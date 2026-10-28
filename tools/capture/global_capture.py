#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一次性「全局抓包」环境（逆向社区签到/兑换协议用，不进产品）。

为什么单独写一个：
    * 产品里的代理（backend/proxy.py）只解密抽卡域名，抓不到社区；
    * 直接跑 main.py 会弹出 pywebview 窗口并接管代理，验收红线禁止（见项目记忆）；
    * 全局抓包必须保证「进程崩了系统代理一定会恢复」，所以复用了
      backend/proxy_watchdog.py 的独立看门狗。

用法：
    python tools/capture/global_capture.py --port 8899 --out .runtime/capture/xxx
    python tools/capture/global_capture.py --port 8899 --out ... --no-proxy   # 只起代理不动系统代理（自检用）

控制：
    * 在 out 目录创建一个名为 stop 的文件 → 正常收尾（恢复系统代理、写 summary.json）；
    * 进程被强杀 → 看门狗在 2 秒内把系统代理恢复原样；
    * 启动时会清理 out 目录里遗留的旧快照（上次被强杀且看门狗也死了的情况）。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mitmproxy import options  # noqa: E402
from mitmproxy.tools.dump import DumpMaster  # noqa: E402

from backend.proxy_watchdog import (  # noqa: E402
    AUTO_CONFIG_URL,
    INTERNET_SETTINGS_KEY,
    PROXY_ENABLE,
    PROXY_OVERRIDE,
    PROXY_SERVER,
    capture_proxy_snapshot,
    load_snapshot,
    merge_proxy_override,
    notify_proxy_change,
    proxy_owned_by_us,
    read_manual_proxy,
    restore_proxy_snapshot,
    write_snapshot,
)

# 这些域名不进 mitmproxy（直接 TCP 透传）：模型/账号类服务一旦被 TLS 拦截，
# 正在跑的对话就可能被证书问题打断。属于自保，不是抓包目标。
DEFAULT_BYPASS = [
    "deepseek.com",
    "deepseek.ai",
    "openai.com",
    "anthropic.com",
]
from recorder import GlobalRecorder  # noqa: E402


def _write_state(out_dir: Path, **fields) -> None:
    path = out_dir / "state.json"
    data = {"updated_at": time.time(), **fields}
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _recover_stale_snapshots(out_dir: Path) -> None:
    """上次被强杀、看门狗也没活下来时，这里兜底恢复系统代理。"""
    for snapshot_path in out_dir.glob("proxy-snapshot-*.json"):
        try:
            snapshot = load_snapshot(snapshot_path)
        except Exception:
            continue
        try:
            if proxy_owned_by_us(snapshot):
                restore_proxy_snapshot(snapshot)
        except Exception as exc:
            print(f"[WARN] 恢复遗留系统代理失败: {exc}")
        for suffix in ("", ".ready", ".stop"):
            candidate = Path(str(snapshot_path).replace(".json", suffix)) if suffix else snapshot_path
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass


def _read_value(key, name: str):
    import winreg

    try:
        return winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None


def apply_proxy_with_bypass(server: str, bypass: list[str]) -> None:
    """把系统代理指向本机，同时把 bypass 域名写进 ProxyOverride（直连，不走代理）。

    与 backend.proxy_watchdog.apply_manual_proxy 的唯一区别就是这条 bypass 追加；
    恢复仍然走 restore_proxy_snapshot（快照里是改动前的原值，与这里无关）。
    """
    import winreg

    if not bypass:
        from backend.proxy_watchdog import apply_manual_proxy

        apply_manual_proxy(server)
        return

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE
    ) as key:
        previous = _read_value(key, PROXY_OVERRIDE)
        previous_override = previous[0] if previous else ""
        override = merge_proxy_override(previous_override)
        items = [item for item in override.split(";") if item]
        seen = {item.lower() for item in items}
        for host in bypass:
            host = host.strip().lstrip("*.")
            if not host:
                continue
            pattern = f"*.{host}"
            if pattern.lower() not in seen:
                items.append(pattern)
                seen.add(pattern.lower())
        override = ";".join(items)

        winreg.SetValueEx(key, PROXY_ENABLE, 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, PROXY_SERVER, 0, winreg.REG_SZ, str(server))
        winreg.SetValueEx(key, PROXY_OVERRIDE, 0, winreg.REG_SZ, override)
        try:
            winreg.DeleteValue(key, AUTO_CONFIG_URL)
        except FileNotFoundError:
            pass

    notify_proxy_change()
    enabled, current = read_manual_proxy()
    if enabled != 1 or current != str(server):
        raise RuntimeError("ProxyEnable/ProxyServer 未生效（可能被组策略覆盖）")
    print(f"[OK] ProxyOverride={override}", flush=True)


class Capture:
    def __init__(self, args, out_dir: Path):
        self.args = args
        self.out_dir = out_dir
        self.stop_path = out_dir / "stop"
        self.token = f"{os.getpid()}-{int(time.time())}"
        self.snapshot_path = out_dir / f"proxy-snapshot-{self.token}.json"
        self.ready_path = out_dir / f"proxy-snapshot-{self.token}.ready"
        self.wd_stop_path = out_dir / f"proxy-snapshot-{self.token}.stop"
        self.server = f"127.0.0.1:{args.port}"
        self.master: DumpMaster | None = None
        self.watchdog = None
        self.recorder = GlobalRecorder(out_dir)
        self._proxy_applied = False
        self._watcher_task = None

    # ---- mitmproxy 生命周期 ----
    def _start_watchdog(self) -> bool:
        command = [
            sys.executable,
            str(Path(__file__).resolve().parent / "watchdog_entry.py"),
            str(os.getpid()),
            str(self.snapshot_path),
            str(self.ready_path),
            str(self.wd_stop_path),
        ]
        creation_flags = 0
        if os.name == "nt":
            creation_flags = (
                getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
        self.watchdog = subprocess.Popen(
            command,
            cwd=str(REPO_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creation_flags,
        )
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if self.ready_path.exists():
                return True
            if self.watchdog.poll() is not None:
                print(f"[WARN] 看门狗提前退出 rc={self.watchdog.returncode}")
                self.watchdog = None
                return False
            time.sleep(0.1)
        print("[WARN] 看门狗启动超时")
        self._stop_watchdog()
        return False

    def _stop_watchdog(self) -> None:
        if self.watchdog is None:
            return
        try:
            self.wd_stop_path.touch(exist_ok=True)
            self.watchdog.wait(timeout=3)
        except Exception:
            try:
                self.watchdog.terminate()
            except Exception:
                pass
        self.watchdog = None

    def _enable_system_proxy(self) -> None:
        _write_state(self.out_dir, status="starting", server=self.server)
        write_snapshot(self.snapshot_path, capture_proxy_snapshot(self.server))
        if not self._start_watchdog():
            raise RuntimeError("看门狗未就绪，拒绝修改系统代理")
        apply_proxy_with_bypass(self.server, self.args.ignore_hosts)
        self._proxy_applied = True
        _write_state(self.out_dir, status="running", server=self.server,
                     snapshot=str(self.snapshot_path),
                     bypass=self.args.ignore_hosts)
        print(f"[READY] 系统代理已指向 {self.server}，全量解密；抓包目录 {self.out_dir}", flush=True)

    def _disable_system_proxy(self) -> None:
        if not self._proxy_applied:
            return
        try:
            snapshot = load_snapshot(self.snapshot_path)
            ok = restore_proxy_snapshot(snapshot)
            print(f"[OK] 系统代理已恢复" if ok else "[WARN] 系统代理已被改动，未强行覆盖")
        except Exception as exc:
            print(f"[WARN] 恢复系统代理失败: {exc}")
        finally:
            self._proxy_applied = False
            try:
                self.snapshot_path.unlink(missing_ok=True)
                self.ready_path.unlink(missing_ok=True)
                self.wd_stop_path.unlink(missing_ok=True)
            except OSError:
                pass

    def running(self) -> None:
        try:
            if self._watcher_task is None:
                self._watcher_task = asyncio.get_event_loop().create_task(self._watch_stop())
            if self.args.no_proxy:
                _write_state(self.out_dir, status="running", server=self.server, mode="no-proxy")
                print(f"[READY] 监听 {self.server}（未改系统代理）；目录 {self.out_dir}", flush=True)
                return
            self._enable_system_proxy()
        except Exception as exc:
            print(f"[FATAL] 启用失败: {exc}", flush=True)
            _write_state(self.out_dir, status="failed", error=str(exc))
            self.master.shutdown()

    async def _watch_stop(self) -> None:
        while not self.stop_path.exists():
            await asyncio.sleep(0.2)
        print("[INFO] 收到 stop 标记，开始收尾", flush=True)
        self.master.shutdown()

    def done(self) -> None:
        self.recorder.done()
        self._disable_system_proxy()
        _write_state(self.out_dir, status="stopped", summary=self.recorder.summary())
        summary = self.recorder.summary()
        (self.out_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[DONE] 共 {summary['flows']} 条流量，{len(summary['hosts'])} 个主机", flush=True)


async def run(args) -> int:
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    _recover_stale_snapshots(out_dir)

    capture = Capture(args, out_dir)
    opts = options.Options(
        listen_host="127.0.0.1",
        listen_port=args.port,
        ssl_insecure=True,
        allow_hosts=[],
        ignore_hosts=[rf".*\.{re.escape(host)}$" for host in args.ignore_hosts],
    )
    if args.confdir:
        opts.confdir = args.confdir

    master = DumpMaster(opts, with_termlog=False, with_dumper=False)
    capture.master = master
    master.addons.add(capture.recorder)
    master.addons.add(capture)

    try:
        await master.run()
    finally:
        if capture._watcher_task is not None:
            capture._watcher_task.cancel()
        capture.done()
        capture._stop_watchdog()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="一次性全局抓包（逆向用）")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--out", required=True, help="抓包输出目录")
    parser.add_argument("--confdir", default="", help="mitmproxy 证书目录（默认 ~/.mitmproxy）")
    parser.add_argument("--no-proxy", action="store_true", help="只起代理，不改系统代理（自检）")
    parser.add_argument(
        "--ignore-hosts",
        nargs="*",
        default=list(DEFAULT_BYPASS),
        help="不走代理/不解密的域名（默认含模型 API）",
    )
    args = parser.parse_args()

    if os.name != "nt" and not args.no_proxy:
        print("仅支持 Windows 的系统代理接管", file=sys.stderr)
        return 2

    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
