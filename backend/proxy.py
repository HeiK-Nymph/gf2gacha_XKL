from pathlib import Path
import sys
import threading
import time
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
    p.enable = True
    p.server = f'{ip}:{port}'
    p.registry_write()
    _update_state(system_proxy=True)


def close_proxy():
    """关闭系统代理"""
    try:
        p.enable = False
        p.registry_write()
    finally:
        _update_state(system_proxy=False)


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


def _watch_ready(port, timeout=15.0):
    """后台探测 mitmproxy 何时真正开始监听，Ready 之后系统代理才是可信的"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _can_connect(port):
            _update_state(ready=True)
            print(f"[OK] mitmproxy 已开始监听 127.0.0.1:{port}")
            return
        time.sleep(0.2)
    _update_state(ready=False, error=f"端口 {port} 在 {timeout:.0f} 秒内没有开始监听")
    print(f"[ERROR] mitmproxy 未能在 {timeout:.0f} 秒内监听端口 {port}")


def load_addons():
    """加载addons目录下的addons.py"""
    addons_dir = Path(__file__).parent / 'addons'
    sys.path.insert(0, str(addons_dir))

    import addons
    return addons.addons


async def run_proxy(port=8080, auto_find_port=True):
    """启动代理服务器

    Args:
        port: 起始端口，默认8080
        auto_find_port: 如果指定端口被占用，是否自动查找可用端口
    """
    global actual_port

    # 如果需要自动查找端口
    if auto_find_port:
        actual_port = find_available_port(port)
        if actual_port != port:
            print(f"[WARN] 端口 {port} 被占用，使用端口 {actual_port}")
            port = actual_port
    else:
        actual_port = port

    _update_state(port=port, ready=False, error=None)
    set_proxy('127.0.0.1', port)

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

    # 加载addons
    for addon in load_addons():
        master.addons.add(addon)

    print(f"[OK] mitmproxy启动成功！监听端口: {port}")
    print("[INFO] 按 Ctrl+C 停止代理")

    # 后台探测端口是否真的可用
    threading.Thread(target=_watch_ready, args=(port,), daemon=True).start()

    # 启动代理
    try:
        await master.run()
    except KeyboardInterrupt:
        print("\n[INFO] 正在停止代理...")
        master.shutdown()
    except Exception as e:
        _update_state(error=str(e))
        print(f"[ERROR] mitmproxy 运行出错: {e}")
        raise
    finally:
        _update_state(ready=False)
        close_proxy()

    return port

if __name__ == '__main__':
    asyncio.run(run_proxy(8080))
