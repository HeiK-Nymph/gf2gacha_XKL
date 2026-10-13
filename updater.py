r"""
独立更新器（v2：先校验，再原子切换，失败自动回滚）
功能：从 R2 下载更新包 -> 校验 -> 解压 -> 原子替换 -> 启动新版本 -> 看门狗守护

设计要点
========
1. **先校验再动手**：size + sha256 + 包结构（exe / 前端 dist / backend / 运行时
   标记 / 文件数）。任何一步不过就中止，安装目录一字不动。
2. **原子切换**：不再"逐个文件先删后拷"，而是把整个 `_internal` 目录改名替换：
      _internal -> _internal_old      （旧版留作回滚备份）
      new/_internal -> _internal      （新版）
   两次改名之间几乎不可能失败，最坏情况是"没换"，不会出现半新半旧。
3. **保住用户数据**：records / certs / logs / cache 都住在 _internal 里，切换前
   先把它们挪到 _update_tmp/preserve，切换完再挪回新版目录，所以抽卡记录、证书、
   日志、图标缓存都不会丢。回滚时同样把它们搬回旧版。
4. **看门狗**：切换完启动新版本，并等它写出"启动成功"（主程序界面起来后
   会调 mark_update_ok 写 state=ok）。
      * 写到了        -> 删掉 _internal_old（不留多余的一份），自己关掉窗口
      * 进程立刻退出  -> 自动回滚到旧版并重新启动旧版
      * 90 秒没写 ok  -> 结束新进程后自动回滚
   判定逻辑抽成纯函数 watchdog_should_rollback()，方便测试。
5. **孤儿清理**：_internal 是整体替换，天然没有残留；根目录只删"明显是构建产物"
   且新包里没有的文件（*.exe/*.dll/*.pyd/base_library.zip/_* 目录），
   用户自己的文件一律不动、只记一条日志。
6. **不走系统代理**（trust_env=False）：主程序会把系统代理指向自己的 mitmproxy，
   主程序被强杀后那个代理是死的，走它必然下载失败。
7. 自己的日志写 logs/updater.log，进度写 logs/update_state.json，主程序下次
   启动能据此提示"上次更新没走完"并支持一键回滚。

手动回滚：updater.exe --rollback
环境变量（仅本地演练用）：GF2XKL_APP_ROOT / GF2XKL_SKIP_LAUNCH /
GF2XKL_WATCHDOG_SECONDS / GF2XKL_MIN_FILES / GF2XKL_MIN_INTERNAL_MB
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import warnings
import zipfile
from pathlib import Path

import requests

warnings.filterwarnings("ignore")
requests.packages.urllib3.disable_warnings()

DEFAULT_VERSION_URL = "https://r2.gf2gacha-xkl.uk/version.json"
DEFAULT_DOWNLOAD_URL = "https://r2.gf2gacha-xkl.uk/gf2gacha_XKL.zip"
MAX_LOG_BYTES = 1 * 1024 * 1024
DEFAULT_WATCHDOG_SECONDS = 90
PRESERVE_DIRS = ("records", "certs", "logs", "cache")
TEMP_DIR_NAME = "_update_tmp"
OLD_INTERNAL_NAME = "_internal_old"
BROKEN_INTERNAL_NAME = "_internal_broken"
# 根目录里"属于我们的构建产物"特征：只有符合这些的才会被当孤儿清理
ROOT_ARTIFACT_SUFFIXES = (".exe", ".dll", ".pyd", ".zip")

# ============================================================
# 日志
# ============================================================
_log_lock = threading.Lock()
_log_file = None
# 切换 _internal 期间日志句柄必须关掉，这几行先进内存，收尾时补写进文件
_log_pending: list = []


def _logs_dir() -> Path:
    return get_internal_path() / "logs"


def setup_logging() -> Path:
    global _log_file
    path = _logs_dir() / "updater.log"
    try:
        _logs_dir().mkdir(parents=True, exist_ok=True)
        try:
            if path.exists() and path.stat().st_size > MAX_LOG_BYTES:
                backup = path.with_name("updater.log.1")
                if backup.exists():
                    backup.unlink()
                path.rename(backup)
        except OSError:
            pass
        _log_file = open(path, "a", encoding="utf-8", buffering=1)
        with _log_lock:
            for buffered in _log_pending:
                _log_file.write(buffered + "\n")
            _log_pending.clear()
    except Exception as exc:
        print(f"[UPDATER] 打开日志文件失败（只输出到控制台）: {exc}")
        _log_file = None
    return path


def close_logging():
    """切换 _internal 之前必须松开日志句柄，否则目录改不了名"""
    global _log_file
    with _log_lock:
        if _log_file is not None:
            try:
                _log_file.close()
            except Exception:
                pass
            _log_file = None


def log(message: str):
    line = f"[{time.strftime('%H:%M:%S')}] {message}"
    with _log_lock:
        try:
            print(line)
        except Exception:
            pass
        if _log_file is not None:
            try:
                _log_file.write(line + "\n")
            except Exception:
                pass
        else:
            _log_pending.append(line)


# ============================================================
# 路径
# ============================================================
def _env_root():
    raw = os.environ.get("GF2XKL_APP_ROOT", "").strip()
    return Path(raw) if raw else None


def get_app_root_path() -> Path:
    r"""安装根目录（gf2gacha_XKL.exe 所在目录）

    更新器可能有两个位置，都要能认出来：
      * 新布局：<安装根目录>\updater.exe          -> 根目录 = exe 所在目录
      * 老布局：<安装根目录>\_internal\updater.exe -> 根目录 = exe 所在目录的上一级
    """
    override = _env_root()
    if override is not None:
        return override
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        if (exe_dir / "_internal").is_dir():
            return exe_dir
        return exe_dir.parent
    return Path(__file__).parent


def get_internal_path() -> Path:
    """_internal 目录（开发环境退化成仓库目录）"""
    root = get_app_root_path()
    internal = root / "_internal"
    return internal if internal.exists() else root


def get_base_path() -> Path:
    return get_internal_path()


# ============================================================
# 状态文件
# ============================================================
def get_state_path() -> Path:
    return _logs_dir() / "update_state.json"


def read_state() -> dict:
    try:
        with open(get_state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        log(f"[UPDATER] 读取状态文件失败: {exc}")
        return {}


def write_state(**fields) -> dict:
    state = read_state()
    state.update(fields)
    state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        path = get_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as exc:
        log(f"[UPDATER] 写状态文件失败: {exc}")
    return state


# ============================================================
# 网络
# ============================================================
SESSION = requests.Session()
SESSION.trust_env = False
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0) gf2gacha_XKL-updater", "Accept": "*/*"})
_adapter = requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=2, pool_block=False)
SESSION.mount("http://", _adapter)
SESSION.mount("https://", _adapter)


def http_get(url, timeout=30):
    return SESSION.get(url, timeout=timeout, verify=False)


def proxy_cleanup():
    """尽力把系统代理恢复成"关闭"状态

    主程序如果被强杀，注册表里会留着指向已经死掉的 mitmproxy 的代理设置，
    那样用户整台机器都上不了网。回滚/收尾时顺手清一下。
    """
    try:
        from winproxy import ProxySetting

        setting = ProxySetting()
        if getattr(setting, "enable", False):
            setting.enable = False
            setting.registry_write()
            log("[UPDATER] 已关闭遗留的系统代理设置")
    except Exception as exc:
        log(f"[UPDATER] 清理系统代理失败（可忽略）: {exc}")


# ============================================================
# 版本 / 检查更新
# ============================================================
def verify_environment():
    version_file = get_internal_path() / "version.json"
    if not version_file.exists():
        return False, None, f"找不到版本文件: {version_file}"
    try:
        data = json.loads(version_file.read_text(encoding="utf-8"))
        local_version = data.get("current_version")
        if not local_version:
            return False, None, "version.json 中缺少 current_version 字段"
        if not data.get("version_url") and not data.get("app_name"):
            return False, None, "version.json 格式不正确，可能是错误的文件"
        return True, local_version, None
    except json.JSONDecodeError:
        return False, None, "version.json 格式错误，无法解析"
    except Exception as e:
        return False, None, f"读取 version.json 失败: {e}"


def _version_tuple(text):
    parts = []
    for chunk in str(text or "").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_update():
    is_valid, local_version, error_msg = verify_environment()
    if not is_valid:
        log(f"[UPDATER] 环境验证失败: {error_msg}")
        log("[UPDATER] 请确保 updater.exe 位于正确的安装目录中；如果是手动运行，请改为运行主程序。")
        return {"has_update": False, "error": f"环境验证失败: {error_msg}", "invalid_environment": True}

    local_data = json.loads((get_internal_path() / "version.json").read_text(encoding="utf-8"))
    version_url = local_data.get("version_url", DEFAULT_VERSION_URL)
    log(f"[UPDATER] 本地版本: {local_version} | 检查地址: {version_url}")
    try:
        remote_data = http_get(version_url, timeout=15).json()
    except Exception as e:
        log(f"[UPDATER] 检查更新失败: {e}")
        return {"has_update": False, "error": str(e)}

    remote_version = remote_data.get("current_version", "0.0.0")
    log(f"[UPDATER] 远程版本: {remote_version}")
    if _version_tuple(remote_version) > _version_tuple(local_version):
        return {
            "has_update": True,
            "local_version": local_version,
            "remote_version": remote_version,
            "download_url": remote_data.get("download_url") or local_data.get("download_url", DEFAULT_DOWNLOAD_URL),
            "sha256": remote_data.get("sha256") or "",
            "size": remote_data.get("size") or 0,
            "update_info": remote_data.get("update_info", ""),
        }
    log("[UPDATER] 当前已是最新版本")
    return {"has_update": False, "local_version": local_version, "remote_version": remote_version}


# ============================================================
# 下载 + 校验
# ============================================================
def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url, dest_path, expected_sha256=None, expected_size=None) -> bool:
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    log(f"[UPDATER] 开始下载: {url}")

    for attempt in range(1, 4):
        try:
            existing = dest_path.stat().st_size if dest_path.exists() else 0
            headers = {"Range": f"bytes={existing}-"} if existing > 0 else {}
            mode = "wb"
            with SESSION.get(url, headers=headers, stream=True, timeout=120, verify=False, allow_redirects=True) as r:
                if existing > 0 and r.status_code == 206:
                    log(f"[UPDATER] 断点续传，从 {existing / 1024 / 1024:.1f}MB 继续")
                    mode = "ab"
                else:
                    existing = 0
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", 0)) + existing
                done = existing
                last_print = 0.0
                with open(dest_path, mode) as f:
                    for chunk in r.iter_content(256 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        now = time.time()
                        if now - last_print >= 1.5:
                            pct = done * 100 / total if total else 0
                            log(f"[UPDATER] {pct:.1f}% | {done / 1024 / 1024:.1f}MB")
                            last_print = now
            break
        except Exception as exc:
            log(f"[UPDATER] 下载失败（第 {attempt}/3 次）: {exc}")
            if attempt == 3:
                return False
            time.sleep(2)

    actual_size = dest_path.stat().st_size
    if expected_size and actual_size != int(expected_size):
        log(f"[UPDATER] 大小校验失败: 实际 {actual_size} / 期望 {expected_size}")
        dest_path.unlink(missing_ok=True)
        return False
    if expected_sha256:
        actual_sha = _sha256_of(dest_path)
        if actual_sha.lower() != str(expected_sha256).lower():
            log(f"[UPDATER] sha256 校验失败!\n  期望 {expected_sha256}\n  实际 {actual_sha}")
            dest_path.unlink(missing_ok=True)
            return False
        log("[UPDATER] sha256 校验通过")
    else:
        log("[UPDATER] 警告：远端未提供 sha256，跳过完整性校验（建议尽快补上）")

    log(f"[UPDATER] 下载完成: {actual_size / 1024 / 1024:.1f} MB")
    return True


# ============================================================
# 包结构校验
# ============================================================
def find_package_root(extract_dir: Path):
    for candidate in (extract_dir / "gf2gacha_XKL", extract_dir / "dist" / "gf2gacha_XKL", extract_dir):
        if candidate.is_dir() and (candidate / "gf2gacha_XKL.exe").exists():
            return candidate
    return None


def validate_package(source_dir: Path, expected_version=None):
    source_dir = Path(source_dir)
    internal = source_dir / "_internal"
    problems = []

    exe = source_dir / "gf2gacha_XKL.exe"
    if not exe.exists():
        problems.append("缺少 gf2gacha_XKL.exe")
    elif exe.stat().st_size < 5 * 1024 * 1024:
        problems.append(f"gf2gacha_XKL.exe 太小（{exe.stat().st_size} 字节），可能没打包完")

    version_file = internal / "version.json"
    package_version = None
    if not version_file.exists():
        problems.append("缺少 _internal/version.json")
    else:
        try:
            package_version = json.loads(version_file.read_text(encoding="utf-8")).get("current_version")
        except Exception as exc:
            problems.append(f"_internal/version.json 无法解析: {exc}")
        if expected_version and package_version and package_version != expected_version:
            problems.append(f"包内版本 {package_version} 与远端声明的 {expected_version} 不一致")

    if not (internal / "frontend" / "dist" / "index.html").exists():
        problems.append("缺少 _internal/frontend/dist/index.html（前端没构建？）")

    backend_files = list((internal / "backend").glob("*.py")) if (internal / "backend").is_dir() else []
    if not backend_files:
        problems.append("缺少 _internal/backend/*.py")

    if not (list(internal.glob("python3*.dll")) or list(internal.glob("base_library.zip"))):
        problems.append("缺少 Python 运行时标记（python3*.dll / base_library.zip）")

    if not (source_dir / "updater.exe").exists() and not (internal / "updater.exe").exists():
        problems.append("缺少 updater.exe")

    min_files = int(os.environ.get("GF2XKL_MIN_FILES", "80") or 80)
    min_internal_mb = float(os.environ.get("GF2XKL_MIN_INTERNAL_MB", "15") or 15)
    file_count = sum(1 for _ in source_dir.rglob("*") if _.is_file())
    internal_size = sum(f.stat().st_size for f in internal.rglob("*") if f.is_file()) if internal.is_dir() else 0
    if file_count < min_files:
        problems.append(f"文件数只有 {file_count}（至少 {min_files}），包不完整")
    if internal_size < min_internal_mb * 1024 * 1024:
        problems.append(f"_internal 只有 {internal_size / 1024 / 1024:.1f}MB（至少 {min_internal_mb}MB），包不完整")

    stats = {
        "file_count": file_count,
        "internal_mb": round(internal_size / 1024 / 1024, 1),
        "package_version": package_version,
    }
    if problems:
        return False, "；".join(problems), stats
    return True, None, stats


# ============================================================
# 用户数据搬迁（records / certs / logs / cache）
# ============================================================
def move_preserve_out(internal: Path, stash: Path) -> list:
    """把用户数据目录从 _internal 挪到临时暂存区"""
    stash.mkdir(parents=True, exist_ok=True)
    moved = []
    for name in PRESERVE_DIRS:
        src = internal / name
        if src.exists():
            dst = stash / name
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.move(str(src), str(dst))
            moved.append(name)
    return moved


def move_preserve_back(stash: Path, internal: Path) -> list:
    """把暂存的用户数据挪回（新的）_internal"""
    restored = []
    internal.mkdir(parents=True, exist_ok=True)
    for name in PRESERVE_DIRS:
        src = stash / name
        if src.exists():
            dst = internal / name
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.move(str(src), str(dst))
            restored.append(name)
    return restored


def cleanup_root_orphans(app_root: Path, keep_names: set):
    """清理根目录里"明显是我们构建产物、但新包里已经没有"的文件

    只删 *.exe/*.dll/*.pyd/*.zip 和 _ 开头的目录；用户自己的文件只记日志不动。
    """
    removed, kept = [], []
    for item in app_root.iterdir():
        name = item.name
        if name in keep_names:
            continue
        looks_like_ours = (item.is_file() and name.lower().endswith(ROOT_ARTIFACT_SUFFIXES)) or (
            item.is_dir() and name.startswith("_")
        )
        if looks_like_ours:
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink()
                removed.append(name)
            except Exception as exc:
                log(f"[UPDATER] 清理根目录残留 {name} 失败: {exc}")
        else:
            kept.append(name)
    if removed:
        log(f"[UPDATER] 已清理根目录里新包不需要的旧文件: {removed}")
    if kept:
        log(f"[UPDATER] 根目录里这些不是本工具的产物，保持不动: {kept}")
    return removed


# ============================================================
# 原子切换
# ============================================================
def _rename_with_retry(src: Path, dst: Path, timeout: float = 30.0) -> bool:
    """改名目录，被占用时重试

    主程序刚退出时它的 dll 可能还被系统释放中，这时改名 _internal 会报
    PermissionError；等一两秒就好了，所以这里重试而不是直接失败。
    """
    deadline = time.time() + timeout
    waited = False
    while True:
        try:
            os.replace(src, dst)
            return True
        except PermissionError as exc:
            if time.time() >= deadline:
                log(f"[UPDATER] 等待文件解锁超时（{timeout:.0f} 秒）: {src.name} -> {dst.name}：{exc}")
                return False
            if not waited:
                log("[UPDATER] 目标仍被占用（主程序可能还没完全退出），等待重试…")
                waited = True
            time.sleep(1.0)


def self_heal(app_root: Path, internal: Path):
    """处理上次更新留下的现场（切换中断时能自愈）"""
    old = app_root / OLD_INTERNAL_NAME
    broken = app_root / BROKEN_INTERNAL_NAME
    if old.exists() and not internal.exists():
        shutil.move(str(old), str(internal))
        log(f"[UPDATER] 检测到上次切换中断，已把 {OLD_INTERNAL_NAME} 恢复成 _internal")
    elif old.exists() and internal.exists():
        # 上次切换成功但没来得及收尾：旧版备份留着也只是占空间
        shutil.rmtree(old, ignore_errors=True)
        log(f"[UPDATER] 清理上次遗留的 {OLD_INTERNAL_NAME}")
    if broken.exists():
        shutil.rmtree(broken, ignore_errors=True)
        log(f"[UPDATER] 清理上次遗留的 {BROKEN_INTERNAL_NAME}")


def atomic_switch(source_dir: Path, temp_dir: Path) -> tuple:
    """原子替换安装目录，返回 (是否成功, 错误信息)"""
    app_root = get_app_root_path()
    internal = get_internal_path()
    new_internal = source_dir / "_internal"
    if not new_internal.is_dir():
        return False, "包内缺少 _internal 目录"

    self_heal(app_root, internal)
    stash = temp_dir / "preserve"

    log("[UPDATER] 松开自己的日志句柄（否则 _internal 改不了名）")
    close_logging()
    try:
        moved = move_preserve_out(internal, stash)
        if moved:
            log(f"[UPDATER] 用户数据已暂存: {moved}")

        # 旧版整体改名成备份
        old_internal = app_root / OLD_INTERNAL_NAME
        if old_internal.exists():
            shutil.rmtree(old_internal, ignore_errors=True)
        if not _rename_with_retry(internal, old_internal):
            return False, "旧版目录改名失败（可能还被占用）"
        log(f"[UPDATER] 旧版已改名为 {OLD_INTERNAL_NAME}")

        # 新版就位
        if not _rename_with_retry(new_internal, internal, timeout=10):
            # 新版没就位就赶紧把旧版换回来，别留下"没有 _internal"的状态
            _rename_with_retry(old_internal, internal, timeout=10)
            return False, "新版目录就位失败，已恢复旧版"
        log("[UPDATER] 新版 _internal 已就位")

        restored = move_preserve_back(stash, internal)
        if restored:
            log(f"[UPDATER] 用户数据已归位: {restored}")

        # 根目录文件替换
        keep_names = {"_internal", OLD_INTERNAL_NAME, TEMP_DIR_NAME, "updater_old.exe"}
        new_root_names = set()
        for item in source_dir.iterdir():
            if item.name == "_internal":
                continue
            new_root_names.add(item.name)
            dest = app_root / item.name
            if item.name == "updater.exe":
                running = app_root / "updater.exe"
                if running.exists():
                    try:
                        running.replace(app_root / "updater_old.exe")
                    except Exception as exc:
                        log(f"[UPDATER] 旧更新器改名失败（可忽略）: {exc}")
            if dest.exists() and dest.is_dir():
                shutil.rmtree(dest, ignore_errors=True)
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        keep_names |= new_root_names
        keep_names |= {"gf2gacha_XKL.exe", "updater.exe"}
        cleanup_root_orphans(app_root, keep_names)
    except Exception as exc:
        setup_logging()
        log(f"[UPDATER] 切换失败: {exc}")
        return False, f"切换失败: {exc}"

    setup_logging()
    write_state(phase="switched")
    log("[UPDATER] 切换完成")
    return True, None


# ============================================================
# 回滚
# ============================================================
def do_rollback(reason: str, relaunch: bool = True) -> bool:
    """把 _internal_old 换回来（用户数据跟着搬回）"""
    app_root = get_app_root_path()
    internal = get_internal_path()
    old_internal = app_root / OLD_INTERNAL_NAME
    broken_internal = app_root / BROKEN_INTERNAL_NAME

    log("=" * 50)
    log(f"[UPDATER] 开始回滚：{reason}")
    if not old_internal.exists():
        log(f"[UPDATER] 找不到回滚备份 {OLD_INTERNAL_NAME}，无法回滚")
        write_state(phase="failed", error=f"回滚失败（没有备份）: {reason}")
        return False

    close_logging()
    try:
        if broken_internal.exists():
            shutil.rmtree(broken_internal, ignore_errors=True)
        if internal.exists():
            if not _rename_with_retry(internal, broken_internal):
                return False, "当前版本目录改名失败（可能还被占用）"
        if not _rename_with_retry(old_internal, internal):
            return False, "旧版目录恢复失败"
        # 用户数据以"新版目录里的那份"为准（它更新）
        if broken_internal.exists():
            stash = app_root / TEMP_DIR_NAME / "preserve_rollback"
            stash.mkdir(parents=True, exist_ok=True)
            move_preserve_out(broken_internal, stash)
            move_preserve_back(stash, internal)
            shutil.rmtree(broken_internal, ignore_errors=True)
    except Exception as exc:
        setup_logging()
        log(f"[UPDATER] 回滚失败: {exc}")
        write_state(phase="failed", error=f"回滚失败: {exc}")
        return False

    setup_logging()
    proxy_cleanup()
    write_state(phase="rolled_back", error=reason)
    log("[UPDATER] 已回滚到上一版本")
    if relaunch:
        launch_main_app()
    return True


# ============================================================
# 看门狗判定（纯函数，方便测试）
# ============================================================
def watchdog_should_rollback(phase: str, proc_alive: bool, elapsed: float, timeout: float) -> str:
    """返回 'ok'（新版启动成功）/ 'rollback:<原因>' / ''（继续等）"""
    if phase == "ok":
        return "ok"
    if not proc_alive:
        return "rollback:新版本启动后立即退出"
    if elapsed >= timeout:
        return f"rollback:新版本 {int(timeout)} 秒内没有完成初始化"
    return ""


# ============================================================
# 执行更新（完整流程）
# ============================================================
def perform_update(download_url, expected_sha256=None, expected_size=None, expected_version=None) -> bool:
    app_root = get_app_root_path()
    temp_dir = app_root / TEMP_DIR_NAME
    zip_path = temp_dir / "update.zip"

    log("=" * 50)
    log("[UPDATER] 开始执行更新...")
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    write_state(phase="downloading")
    if not download_file(download_url, zip_path, expected_sha256, expected_size):
        write_state(phase="failed", error="下载或校验失败")
        log("[UPDATER] 更新终止（下载/校验阶段），安装目录未做任何改动")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False
    write_state(phase="verified")

    extract_dir = temp_dir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            bad = zip_ref.testzip()
            if bad:
                raise RuntimeError(f"压缩包内文件损坏: {bad}")
            zip_ref.extractall(extract_dir)
    except Exception as e:
        write_state(phase="failed", error=f"解压失败: {e}")
        log(f"[UPDATER] 解压失败: {e}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False

    source_dir = find_package_root(extract_dir)
    if source_dir is None:
        write_state(phase="failed", error="压缩包结构不对，找不到 gf2gacha_XKL.exe")
        log("[UPDATER] 压缩包结构不对")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False

    ok, reason, stats = validate_package(source_dir, expected_version)
    log(f"[UPDATER] 包结构校验: {'通过' if ok else '失败'} {stats}")
    if not ok:
        write_state(phase="failed", error=f"包结构校验失败: {reason}")
        log(f"[UPDATER] 包结构校验失败: {reason}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False
    write_state(phase="extracted", package_version=stats.get("package_version"))

    write_state(phase="switching")
    ok, reason = atomic_switch(source_dir, temp_dir)
    if not ok:
        write_state(phase="failed", error=reason)
        log(f"[UPDATER] {reason}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False

    shutil.rmtree(temp_dir, ignore_errors=True)
    return True


def launch_main_app():
    app_root = get_app_root_path()
    main_exe = app_root / "gf2gacha_XKL.exe"
    if not main_exe.exists():
        log("[UPDATER] 找不到主程序 gf2gacha_XKL.exe")
        return None
    try:
        proc = subprocess.Popen(
            [str(main_exe)],
            cwd=str(app_root),
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        log(f"[UPDATER] 已启动主程序: {main_exe}")
        return proc
    except Exception as e:
        log(f"[UPDATER] 启动主程序失败: {e}")
        return None


def wait_for_new_version_started(proc) -> str:
    """看门狗：等新版本把 state 写成 ok"""
    timeout = float(os.environ.get("GF2XKL_WATCHDOG_SECONDS", DEFAULT_WATCHDOG_SECONDS) or DEFAULT_WATCHDOG_SECONDS)
    log(f"[UPDATER] 等待新版本启动完成（最多 {int(timeout)} 秒）...")
    started = time.time()
    while True:
        elapsed = time.time() - started
        phase = read_state().get("phase") or ""
        alive = bool(proc is not None and proc.poll() is None)
        decision = watchdog_should_rollback(phase, alive, elapsed, timeout)
        if decision == "ok":
            log("[UPDATER] 新版本启动成功")
            return "ok"
        if decision.startswith("rollback:"):
            log(f"[UPDATER] {decision.split(':', 1)[1]} -> 自动回滚")
            if alive and proc is not None:
                try:
                    proc.terminate()
                    proc.wait(timeout=10)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            return decision
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="gf2gacha_XKL 独立更新器")
    parser.add_argument("--rollback", action="store_true", help="把上一版本换回来")
    parser.add_argument("--reason", default="用户手动回滚", help="回滚原因（写进日志）")
    parser.add_argument("--url", default="", help="直接指定更新包地址")
    parser.add_argument("--sha256", default="", help="更新包 sha256")
    parser.add_argument("--size", default="", help="更新包字节数")
    parser.add_argument("--to", default="", help="目标版本号")
    args, _ = parser.parse_known_args()

    setup_logging()
    log("=" * 50)
    log("GF2gacha_XKL 独立更新器")
    log(f"[UPDATER] 安装根目录: {get_app_root_path()}")
    log("=" * 50)

    if args.rollback:
        ok = do_rollback(args.reason)
        if ok:
            log("[UPDATER] 回滚完成，3 秒后自动关闭窗口")
            time.sleep(3)
            return
        print("\n按回车键退出...")
        input()
        return

    state = read_state()
    if args.url:
        intent = {"download_url": args.url, "sha256": args.sha256, "size": args.size, "to": args.to}
    elif state.get("phase") == "starting" and state.get("download_url"):
        intent = {
            "download_url": state.get("download_url"),
            "sha256": state.get("sha256") or "",
            "size": state.get("size") or "",
            "to": state.get("to") or "",
        }
        log(f"[UPDATER] 使用主程序留下的更新意图: {intent.get('to')} ({intent['download_url']})")
    else:
        result = check_update()
        if result.get("invalid_environment"):
            log("[UPDATER] 更新器终止运行")
            print("\n按回车键退出...")
            input()
            return
        if not result.get("has_update"):
            print("\n按回车键退出...")
            input()
            return
        intent = {
            "download_url": result.get("download_url"),
            "sha256": result.get("sha256") or "",
            "size": result.get("size") or "",
            "to": result.get("remote_version") or "",
        }

    size = int(intent["size"]) if str(intent.get("size") or "").isdigit() else 0
    success = perform_update(
        intent["download_url"],
        expected_sha256=intent.get("sha256") or None,
        expected_size=size or None,
        expected_version=intent.get("to") or None,
    )

    if not success:
        log("[UPDATER] 更新未完成，安装目录保持原样（旧版本仍可用）")
        print("\n按回车键退出...")
        input()
        return

    if os.environ.get("GF2XKL_SKIP_LAUNCH", "").strip() == "1":
        log("[UPDATER] 跳过启动与看门狗（演练模式）")
        return

    proc = launch_main_app()
    decision = wait_for_new_version_started(proc)
    if decision == "ok":
        old_internal = get_app_root_path() / OLD_INTERNAL_NAME
        if old_internal.exists():
            shutil.rmtree(old_internal, ignore_errors=True)
            log(f"[UPDATER] 已删除回滚备份 {OLD_INTERNAL_NAME}（不再占空间）")
        log("[UPDATER] 更新全部完成，3 秒后自动关闭窗口")
        time.sleep(3)
        return

    do_rollback(decision.split(":", 1)[1])
    log("[UPDATER] 已回滚，请把 updater.log 发给开发者")
    print("\n按回车键退出...")
    input()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"[UPDATER] 发生致命错误: {e}")
        import traceback
        traceback.print_exc()
        print("\n按回车键退出...")
        input()
        sys.exit(1)
