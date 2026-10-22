from pathlib import Path
import atexit
import asyncio
import os
import socket
import subprocess
import sys
import threading
import time
import uuid

from mitmproxy import options
from mitmproxy.tools.dump import DumpMaster

from backend.proxy_watchdog import (
    apply_manual_proxy,
    capture_proxy_snapshot,
    load_snapshot,
    proxy_owned_by_us,
    restore_proxy_snapshot,
    write_snapshot,
)

# 只解密抽卡记录接口：系统代理指向本机 mitmproxy，其余域名由 allow_hosts
# 原样透传（不解密、不校验证书），因此整机上网不受证书和抓包逻辑影响。
TARGET_DOMAINS = ("gf2-gacha-record.sunborngame.com",)

# 全局变量：保存实际使用的端口号（保留旧接口，兼容已有调用）
actual_port = None

# 代理运行状态：给界面展示，也给主程序判断「现在能不能拦到请求」
#   ready=False 时绝不能再改系统代理，否则用户会直接断网且什么都抓不到
proxy_state = {
    "port": None,
    "ready": False,
    "system_proxy": False,
    "mode": "none",
    "targets": list(TARGET_DOMAINS),
    "error": None,
}
_state_lock = threading.Lock()
_lifecycle_lock = threading.RLock()
_active_master = None
_active_stop = None
_proxy_lease = None
_watchdog_process = None


def get_proxy_status() -> dict:
    """返回代理状态快照（不抛异常）"""
    with _state_lock:
        return dict(proxy_state)


def _update_state(**kwargs):
    with _state_lock:
        proxy_state.update(**kwargs)


def _runtime_dir() -> Path:
    override = os.environ.get("GF2XKL_PROXY_DIR", "").strip()
    if override:
        root = Path(override)
    else:
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        root = Path(local_appdata) / "gf2gacha_XKL" if local_appdata else Path.home() / ".gf2gacha_XKL"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _target_domains() -> list[str]:
    override = os.environ.get("GF2XKL_PROXY_TARGETS", "").strip()
    if override:
        domains = [item.strip().lower() for item in override.split(",") if item.strip()]
        if domains:
            return domains
    return list(TARGET_DOMAINS)


def _allow_host_patterns(domains: list[str] | None = None) -> list[str]:
    """mitmproxy allow_hosts：只有匹配的域名会被解密，其余连接原样转发。"""
    import re

    return [r".*" + re.escape(domain) + r".*" for domain in (domains or _target_domains())]


def _make_options(port: int, cert_dir):
    """构造 mitmproxy 选项；allow_hosts 让非目标域名原样透传。"""
    allow = _allow_host_patterns()
    try:
        return options.Options(
            listen_port=port,
            ssl_insecure=True,
            confdir=str(cert_dir),
            allow_hosts=allow,
        )
    except Exception as exc:
        print(f"[WARN] allow_hosts 设置失败({exc})，退回仅自定义证书目录")
        try:
            return options.Options(
                listen_port=port,
                ssl_insecure=True,
                confdir=str(cert_dir),
            )
        except Exception as exc2:
            print(f"[WARN] 自定义证书目录设置失败({exc2})，回退默认配置（TLS 拦截可能失败）")
            return options.Options(listen_port=port, ssl_insecure=True)


def _certificate_is_trusted() -> bool:
    """证书没装时不动系统代理，避免游戏请求被不可信证书打断。"""
    try:
        from backend.cert_generator import (
            check_certificate_installed_windows,
            ensure_ca_certificate,
            get_certificate_info,
        )

        cert_dir, _ = ensure_ca_certificate()
        cert_path = cert_dir / "mitmproxy-ca-cert.cer"
        if not cert_path.exists():
            return False
        info = get_certificate_info(cert_path)
        cert_name = info.get("common_name") if isinstance(info, dict) else None
        return bool(cert_name and check_certificate_installed_windows(cert_name))
    except Exception as exc:
        print(f"[WARN] 无法确认 mitmproxy 证书状态，暂不接管系统代理: {exc}")
        return False


def _start_watchdog(snapshot_path: Path, ready_path: Path, stop_path: Path) -> bool:
    """启动独立看门狗，并等待它确认已经握住主进程句柄。"""
    global _watchdog_process

    if _watchdog_process is not None and _watchdog_process.poll() is None:
        return True

    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command.append(str(Path(sys.argv[0]).resolve()))
    command.extend([
        "--proxy-watchdog",
        str(os.getpid()),
        str(snapshot_path),
        str(ready_path),
        str(stop_path),
    ])

    creation_flags = 0
    if os.name == "nt":
        creation_flags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

    try:
        _watchdog_process = subprocess.Popen(
            command,
            cwd=str(Path(sys.argv[0]).resolve().parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creation_flags,
        )
    except Exception as exc:
        print(f"[WARN] 启动代理看门狗失败: {exc}")
        _watchdog_process = None
        return False

    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        if ready_path.exists():
            return True
        if _watchdog_process.poll() is not None:
            print(f"[WARN] 代理看门狗提前退出，返回码={_watchdog_process.returncode}")
            _watchdog_process = None
            return False
        time.sleep(0.1)

    print("[WARN] 代理看门狗启动超时，未修改系统代理")
    try:
        _watchdog_process.terminate()
    except Exception:
        pass
    _watchdog_process = None
    return False


def _stop_watchdog(stop_path: Path | None = None) -> None:
    global _watchdog_process
    process = _watchdog_process
    if process is None:
        return
    if stop_path is not None:
        try:
            stop_path.touch(exist_ok=True)
        except OSError:
            pass
    if process.poll() is None:
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                process.terminate()
                process.wait(timeout=1)
            except Exception:
                pass
    _watchdog_process = None


def _cleanup_lease_files(lease: dict) -> None:
    for key in ("snapshot_path", "ready_path", "stop_path"):
        value = lease.get(key)
        if not value:
            continue
        try:
            Path(value).unlink(missing_ok=True)
        except OSError:
            pass


def _recover_stale_proxy_state() -> None:
    """恢复上次主程序与看门狗同时被强杀时遗留的本工具代理。"""
    runtime = _runtime_dir()
    for snapshot_path in runtime.glob("gf2-proxy-*.json"):
        try:
            snapshot = load_snapshot(snapshot_path)
            if proxy_owned_by_us(snapshot) and not restore_proxy_snapshot(snapshot):
                continue
            snapshot_path.unlink(missing_ok=True)
            for suffix in (".ready", ".stop"):
                snapshot_path.with_suffix(suffix).unlink(missing_ok=True)
        except Exception as exc:
            print(f"[WARN] 清理遗留系统代理失败: {exc}")


def set_proxy(ip, port):
    """把系统代理指向本机 mitmproxy，并在修改注册表前先启动崩溃看门狗。

    只有 TARGET_DOMAINS 会被 mitmproxy 解密；其余流量由 mitmproxy 原样透传，
    所以证书没装、或抓包逻辑出错，都不会让整台机器断网。
    """
    global _proxy_lease

    with _lifecycle_lock:
        if _active_stop is not None and _active_stop.is_set():
            return False
        if os.name != "nt":
            _update_state(error="定向代理仅支持 Windows")
            return False

        server = f"{ip}:{int(port)}"
        if _proxy_lease is not None:
            snapshot_path = Path(str(_proxy_lease.get("snapshot_path") or ""))
            if _proxy_lease.get("server") == server and snapshot_path.is_file():
                _update_state(system_proxy=True, mode="targeted_tunnel", error=None)
                return True
            print("[WARN] 代理配置已变化，先恢复上一份系统代理设置")
            close_proxy()

        _recover_stale_proxy_state()

        if not _certificate_is_trusted():
            _update_state(system_proxy=False, mode="none", error="mitmproxy 证书未安装或不可信")
            print("[WARN] mitmproxy 证书未安装，已保持系统代理不变")
            return False

        token = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        runtime = _runtime_dir()
        snapshot_path = runtime / f"gf2-proxy-{token}.json"
        ready_path = runtime / f"gf2-proxy-{token}.ready"
        stop_path = runtime / f"gf2-proxy-{token}.stop"
        lease = {
            "server": server,
            "port": int(port),
            "snapshot_path": str(snapshot_path),
            "ready_path": str(ready_path),
            "stop_path": str(stop_path),
        }

        try:
            write_snapshot(snapshot_path, capture_proxy_snapshot(server))

            if not _start_watchdog(snapshot_path, ready_path, stop_path):
                _cleanup_lease_files(lease)
                _update_state(system_proxy=False, mode="none", error="代理看门狗启动失败")
                return False

            if _active_stop is not None and _active_stop.is_set():
                _stop_watchdog(stop_path)
                _cleanup_lease_files(lease)
                return False

            apply_manual_proxy(server)
            _proxy_lease = lease
            _update_state(
                system_proxy=True,
                mode="targeted_tunnel",
                targets=_target_domains(),
                error=None,
            )
            print(
                f"[OK] 已启用系统代理: {server} "
                f"(仅 {', '.join(_target_domains())} 会被解密，其它流量直通)"
            )
            return True
        except Exception as exc:
            try:
                restore_proxy_snapshot(load_snapshot(snapshot_path))
            except Exception:
                pass
            _stop_watchdog(stop_path)
            _cleanup_lease_files(lease)
            _update_state(system_proxy=False, mode="none", error=str(exc))
            print(f"[ERROR] 启用系统代理失败: {exc}")
            return False


def close_proxy():
    """恢复启动前的系统代理设置；失败时保留看门狗等待主进程退出后重试。"""
    global _proxy_lease

    with _lifecycle_lock:
        lease = _proxy_lease
        if lease is not None:
            restored = False
            try:
                snapshot = load_snapshot(lease["snapshot_path"])
                restored = restore_proxy_snapshot(snapshot)
                if not restored:
                    restored = not proxy_owned_by_us(snapshot)
            except Exception as exc:
                print(f"[WARN] 恢复系统代理失败，看门狗将继续兜底: {exc}")

            if restored:
                _stop_watchdog(Path(lease["stop_path"]))
                _cleanup_lease_files(lease)
                _proxy_lease = None
            else:
                print("[WARN] 当前代理设置仍指向本工具，保留看门狗等待进程退出后恢复")
        _update_state(system_proxy=False, mode="none")


def stop_proxy():
    """可从窗口事件线程调用；即使代理还在启动，也不允许随后接管系统代理。"""
    with _lifecycle_lock:
        if _active_stop is not None:
            _active_stop.set()
        try:
            if _active_master is not None:
                _active_master.shutdown()  # mitmproxy 提供的线程安全接口
        finally:
            _update_state(ready=False)
            close_proxy()


def is_port_available(port):
    """检查端口是否可用"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', port))
            return True
    except OSError:
        return False


def find_available_port(start_port=8080, max_attempts=100):
    """从指定端口开始查找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port):
            return port
    raise RuntimeError(f"无法在 {start_port}-{start_port + max_attempts} 范围内找到可用端口")


def _can_connect(port, timeout=0.3):
    """探测本机端口是否已经有人在监听"""
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=timeout):
            return True
    except OSError:
        return False


def load_addons():
    """加载addons目录下的addons.py"""
    addons_dir = Path(__file__).parent / 'addons'
    sys.path.insert(0, str(addons_dir))

    import addons
    return addons.addons


async def run_proxy(port=8080, auto_find_port=True, stop_event=None):
    """启动代理服务器

    Args:
        port: 起始端口，默认8080
        auto_find_port: 如果指定端口被占用，是否自动查找可用端口
    """
    global actual_port, _active_master, _active_stop
    stop_event = stop_event if stop_event is not None else threading.Event()
    if stop_event.is_set():
        return

    # 如果需要自动查找端口
    if auto_find_port:
        actual_port = find_available_port(port)
        if actual_port != port:
            print(f"[WARN] 端口 {port} 被占用，使用端口 {actual_port}")
            port = actual_port
    else:
        actual_port = port

    _update_state(port=port, ready=False, error=None)

    # 确保证书存在，不存在则自动生成
    from backend.cert_generator import ensure_ca_certificate, generate_user_ca_certificate
    cert_dir, is_new = ensure_ca_certificate()
    if is_new:
        cert_dir = generate_user_ca_certificate()

    # 配置选项：allow_hosts 让抽卡域名以外的流量原样透传
    opts = _make_options(port, cert_dir)

    # 创建DumpMaster对象
    #   with_termlog=False  关掉终端日志
    #   with_dumper=False   关掉「每条 flow 都打到 stdout」的 dumper
    master = DumpMaster(opts, with_termlog=False, with_dumper=False)

    class Lifecycle:
        def running(self):
            # RunningHook 在监听器建立后触发；与退出操作串行，防止关闭后重新启用代理。
            with _lifecycle_lock:
                if stop_event.is_set():
                    master.shutdown()
                    return
                try:
                    if not _can_connect(port):
                        raise RuntimeError(f'代理端口 {port} 未开始监听')
                    enabled = set_proxy('127.0.0.1', port)
                    _update_state(ready=True)
                    if enabled:
                        print(f'[OK] mitmproxy 已就绪并启用系统代理: 127.0.0.1:{port}')
                    else:
                        print('[WARN] mitmproxy 已就绪，但系统代理未接管（通常是证书未安装）')
                except Exception as exc:
                    _update_state(error=str(exc))
                    master.shutdown()

    # 即使在 run() 初始化期间退出，也会在下一次事件循环迭代发出停止信号。
    async def watch_stop():
        while not stop_event.is_set():
            await asyncio.sleep(.1)
        master.shutdown()

    # 启动代理
    watcher = None
    try:
        with _lifecycle_lock:
            _active_master, _active_stop = master, stop_event
        for addon in load_addons():
            master.addons.add(addon)
        master.addons.add(Lifecycle())
        watcher = asyncio.create_task(watch_stop())
        await master.run()
    except KeyboardInterrupt:
        print("\n[INFO] 正在停止代理...")
        master.shutdown()
    except Exception as e:
        _update_state(error=str(e))
        print(f"[ERROR] mitmproxy 运行出错: {e}")
        raise
    finally:
        if watcher is not None:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
        with _lifecycle_lock:
            _active_master, _active_stop = None, None
            _update_state(ready=False)
            close_proxy()

    return port


atexit.register(close_proxy)

if __name__ == '__main__':
    asyncio.run(run_proxy(8080))