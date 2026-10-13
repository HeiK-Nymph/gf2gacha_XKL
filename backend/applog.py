#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""日志模块：把 print / logging / 未捕获异常写进 logs/app.log

打包后的主程序是 console=False（见 gf2gacha_XKL.spec），print 出来的东西
用户和开发者都看不到，所以日志文件是排障的唯一证据。

但用户反馈「日志里全是没用的东西、文件一直涨」，典型噪声有两类：
    * mitmproxy 把每一条连接都打出来：server connect config.edge.skype.com:443 (...)
    * pywebview 反射 .NET 类型失败，打印一长串 window.native.xxx.Empty.Empty.Empty...
因此这里做了四层处理：

    1. 只记录「我们自己的」输出：第三方 logger（mitmproxy / pywebview / urllib3 …）
       的记录直接被 filter 丢掉，也不会落到 Python 的 lastResort 处理里；
    2. 行级过滤：连接日志、flow 行、"Error while processing window.native" 之类的
       噪声行整行丢弃，并定期汇报"过滤了多少行"；
    3. 行整形：连续重复的行合并成「上一行重复 N 次」，超长行截断，
       `.Empty.Empty.Empty...` 这种重复片段折叠成 `.Empty×38`；
    4. 日志超过上限自动轮转成 app.log.1（启动时 + 运行期都会检查），
       不会无限增长。
"""
from __future__ import annotations

import io
import logging
import re
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "app.log"
MAX_BYTES = 2 * 1024 * 1024      # 超过 2MB 轮转成 app.log.1
MAX_LINE_CHARS = 1000            # 单行上限，避免 pywebview 那种超长行

# 这些 logger 的输出一律不进日志文件（第三方库的内部日志）
_THIRD_PARTY_LOGGERS = (
    "mitmproxy", "webview", "pywebview", "aiohttp", "urllib3", "asyncio",
    "PIL", "matplotlib", "clr", "pythonnet", "comtypes", "selenium",
)

# 只保留这些前缀的 logger（我们自己的模块）
_OUR_LOGGERS = ("backend", "gf2gacha", "main", "__main__")

# 噪声行特征
_NOISE_PATTERNS = (
    re.compile(r"^\s*(?:server|client)\s+(?:connect|disconnect|eof|error)\b", re.I),
    re.compile(r"^\s*\[?\s*(?:mitmproxy|pywebview)\b", re.I),
    re.compile(r"Error while processing window\.native"),
    re.compile(r"__abstractmethods__"),
    # mitmproxy dumper / termlog 的 flow 输出形态：
    #   127.0.0.1:1469: GET http://example.com/
    #                << 200 OK 334b
    re.compile(r"^[\w.\-\[\]:]+:\s*(?:GET|POST|PUT|DELETE|HEAD|OPTIONS|CONNECT|PATCH)\s+\S+", re.I),
    re.compile(r"^\s*(?:<<|>>)\s*\d{3}\b"),
    re.compile(r"^\s*<?(?:GET|POST|PUT|DELETE|HEAD|CONNECT|OPTIONS)\s+https?://"),
    re.compile(r"InsecureRequestWarning"),
    re.compile(r"^\s*\((?:\d+\.\d+\.\d+\.\d+:\d+)\s+(?:client|server)\)"),  # mitmproxy 地址行
)

_EMPTY_RUN = re.compile(r"(?:\.Empty){2,}")


def _shrink(line: str) -> str:
    """折叠重复片段、截断超长行"""
    line = _EMPTY_RUN.sub(lambda m: f".Empty×{len(m.group(0)) // len('.Empty')}", line)
    if len(line) > MAX_LINE_CHARS:
        line = line[:MAX_LINE_CHARS] + f"...（已截断，原长 {len(line)} 字符）"
    return line


def _is_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return any(pattern.search(stripped) for pattern in _NOISE_PATTERNS)


class _LogSink:
    """带过滤 / 去重 / 截断 / 自动轮转的日志文件写入器"""

    def __init__(self, path: Path, max_bytes: int = MAX_BYTES):
        self.path = path
        self.max_bytes = max_bytes
        self._lock = threading.RLock()
        self._buffer = ""
        self._last_line: str | None = None
        self._repeat = 0
        self._dropped = 0
        self._dropped_reported = 0
        self._written = 0
        self._handle = self._open()

    # ---------- 文件管理 ----------
    def _open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rotate_if_needed()
        return open(self.path, "a", encoding="utf-8", buffering=1)

    def _rotate_if_needed(self):
        try:
            if self.path.exists() and self.path.stat().st_size > self.max_bytes:
                backup = self.path.with_name(self.path.name + ".1")
                if backup.exists():
                    backup.unlink()
                self.path.rename(backup)
                return True
        except OSError:
            pass
        return False

    def _rotate_running(self):
        try:
            self._handle.close()
        except Exception:
            pass
        self._rotate_if_needed()
        try:
            self._handle = open(self.path, "a", encoding="utf-8", buffering=1)
            self._raw_write(f"[LOG] 日志已达 {self.max_bytes // 1024} KB，已轮转到 app.log.1")
        except Exception:
            pass

    def _raw_write(self, line: str):
        try:
            self._handle.write(line + "\n")
            self._written += 1
            if self._written % 200 == 0 and self.path.stat().st_size > self.max_bytes:
                self._rotate_running()
        except Exception:
            pass

    # ---------- 对外接口（当成一个可写的 text stream） ----------
    def write(self, text) -> int:
        if not isinstance(text, str):
            text = str(text)
        with self._lock:
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                self._emit(line)
        return len(text)

    def _emit(self, line: str):
        line = _shrink(line)
        if _is_noise(line):
            self._dropped += 1
            # 长跑会话里也偶尔报一次总数，方便确认过滤在工作
            if self._dropped % 500 == 0:
                self._report_dropped()
            return
        if line == self._last_line:
            self._repeat += 1
            return
        self._flush_repeat()
        self._last_line = line
        self._raw_write(line)

    def _report_dropped(self):
        if self._dropped > self._dropped_reported:
            self._raw_write(
                f"[LOG] 已过滤 {self._dropped} 行第三方噪声日志（mitmproxy 连接日志 / pywebview 反射告警等）"
            )
            self._dropped_reported = self._dropped

    def _flush_repeat(self):
        if self._repeat:
            self._raw_write(f"        ^^^ 上一行重复 {self._repeat} 次")
            self._repeat = 0

    def flush(self):
        with self._lock:
            if self._buffer:
                self._emit(self._buffer)
                self._buffer = ""
            self._flush_repeat()
            self._report_dropped()
            try:
                self._handle.flush()
            except Exception:
                pass

    def close(self):
        self.flush()
        try:
            self._handle.close()
        except Exception:
            pass


class _Tee(io.TextIOBase):
    """把写入同时转发给控制台和日志文件（文件侧带过滤）"""

    def __init__(self, console, sink: "_LogSink", lock=None):
        self._console = console
        self._sink = sink
        self._lock = lock or threading.Lock()

    @property
    def encoding(self):
        return "utf-8"

    @property
    def errors(self):
        return "replace"

    def writable(self):
        return True

    def writelines(self, lines):  # type: ignore[override]
        for line in lines:
            self.write(line)

    def write(self, text):  # type: ignore[override]
        if not isinstance(text, str):
            text = str(text)
        with self._lock:
            if self._console is not None:
                try:
                    self._console.write(text)
                    self._console.flush()
                except Exception:
                    pass
            self._sink.write(text)
        return len(text)

    def flush(self):  # type: ignore[override]
        with self._lock:
            if self._console is not None:
                try:
                    self._console.flush()
                except Exception:
                    pass
            # 注意：这里刻意不把不完整的行推给文件，避免 print 的 "文本" + "\n"
            # 两次 write 被拆成两条日志；真正的 flush 由 sink 自己按行处理

    def isatty(self):
        return False

    def fileno(self):
        if self._console is not None:
            try:
                return self._console.fileno()
            except Exception:
                pass
        raise io.UnsupportedOperation("fileno")

    def close(self):
        self.flush()

    def __getattr__(self, name):
        console = self.__dict__.get("_console")
        if console is not None:
            try:
                return getattr(console, name)
            except AttributeError:
                pass
        raise AttributeError(name)


class _OnlyOurLoggers(logging.Filter):
    """允许 root 上的 handler 存在（挡住 lastResort），但只放行我们自己的日志"""

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name or ""
        if not name:
            return True
        if name.startswith(_THIRD_PARTY_LOGGERS):
            return False
        return name.startswith(_OUR_LOGGERS)


_setup_done = False
_log_path = None
_sink: _LogSink | None = None


def setup_logging(log_dir: Path | str | None = None, max_bytes: int = MAX_BYTES) -> Path:
    """初始化日志，返回日志文件路径（重复调用只生效一次）"""
    global _setup_done, _log_path, _sink
    if _setup_done and _log_path is not None:
        return _log_path

    directory = Path(log_dir) if log_dir else LOG_DIR
    path = directory / "app.log"

    try:
        _sink = _LogSink(path, max_bytes=max_bytes)
    except Exception as exc:  # 目录不可写也不能让程序起不来
        print(f"[WARNING] 初始化日志失败（将只输出到控制台）: {exc}")
        _setup_done = True
        _log_path = path
        return path

    lock = threading.Lock()
    original_out, original_err = sys.stdout, sys.stderr
    sys.stdout = _Tee(original_out, _sink, lock=lock)
    sys.stderr = _Tee(original_err, _sink, lock=lock)

    # 让 urllib3 的 InsecureRequestWarning 闭嘴（本工具就是用自签 CA + verify=False）
    try:
        import warnings

        from urllib3.exceptions import InsecureRequestWarning

        warnings.filterwarnings("ignore", category=InsecureRequestWarning)
    except Exception:
        pass

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.addFilter(_OnlyOurLoggers())
        root.addHandler(handler)
    # 第三方库内部日志压到 ERROR，从源头少产生噪声
    for name in _THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(logging.ERROR)

    def _handle_exception(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return
        print("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))

    sys.excepthook = _handle_exception

    def _thread_hook(args):
        print("".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))

    try:
        threading.excepthook = _thread_hook
    except Exception:
        pass

    _setup_done = True
    _log_path = path
    print("=" * 60)
    print(f"[LOG] 日志文件: {path}  启动时间: {datetime.now():%Y-%m-%d %H:%M:%S}")
    return path


def get_log_path() -> Path | None:
    return _log_path


def read_log_tail(max_chars: int = 200_000) -> str:
    """读取日志尾部（供界面的日志窗口显示）"""
    global _sink
    try:
        if _sink is not None:
            _sink.flush()
    except Exception:
        pass
    path = _log_path or LOG_FILE
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return "（暂无日志）"
    except Exception as exc:
        return f"（读取日志失败: {exc}）"
    if len(text) > max_chars:
        text = "（仅显示日志尾部）\n" + text[-max_chars:]
    return text or "（暂无日志）"
