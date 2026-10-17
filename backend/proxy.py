from pathlib import Path
import sys
import threading
import socket
import asyncio
from mitmproxy import options
from mitmproxy.tools.dump import DumpMaster
from winproxy import ProxySetting

# 全局变量：保存实际使用的端口号（保留旧接口，兼容已有调用）
actual_port = None

# 代理运行状态：给界面展示，也给主程序判断「现在能不能拦到请求」
#   ready=False 时绝不能再改系统代理，否则用户会直接断网且什么都抓不到
proxy_state = {
    "port": None,
    "ready": False,
    "system_proxy": False,
    "error": None,
}
_state_lock = threading.Lock()
_lifecycle_lock = threading.RLock()
_active_master = None
_active_stop = None
_previous_proxy = None

p = ProxySetting()


def get_proxy_status() -> dict:
    """返回代理状态快照（不抛异常）"""
    with _state_lock:
        return dict(proxy_state)


def _update_state(**kwargs):
    with _state_lock:
        proxy_state.update(**kwargs)


def set_proxy(ip, port):
    """设置系统代理"""
    global _previous_proxy
    with _lifecycle_lock:
        if _active_stop is not None and _active_stop.is_set():
            return False
        if _previous_proxy is None:
            previous = ProxySetting()
            previous.registry_read()
            _previous_proxy = previous
        p.enable = True
        p.server = f'{ip}:{port}'
        p.registry_write()
        _update_state(system_proxy=True)
        return True


def close_proxy():
    """只恢复本程序接管前的代理设置；未接管时不改用户设置。"""
    global _previous_proxy
    with _lifecycle_lock:
        if _previous_proxy is not None:
            _previous_proxy.registry_write()
            _previous_proxy = None
        _update_state(system_proxy=False)


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

    # 配置选项
    try:
        opts = options.Options(
            listen_port=port,
            ssl_insecure=True,
            confdir=str(cert_dir)  # 使用项目专属证书目录
        )
    except Exception as e:
        # 不同 mitmproxy 版本对 confdir 的处理不同，退化也不能让代理起不来
        print(f"[WARN] 自定义证书目录设置失败({e})，回退默认配置（TLS 拦截可能失败）")
        opts = options.Options(listen_port=port, ssl_insecure=True)

    # 创建DumpMaster对象
    #   with_termlog=False  关掉终端日志
    #   with_dumper=False   关掉「每条 flow 都打到 stdout」的 dumper
    #                       （默认是 True，日志文件会被 127.0.0.1:1469: GET http://... 刷满）
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
                    set_proxy('127.0.0.1', port)
                    _update_state(ready=True)
                    print(f'[OK] mitmproxy 已就绪并接管系统代理: 127.0.0.1:{port}')
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

if __name__ == '__main__':
    asyncio.run(run_proxy(8080))
