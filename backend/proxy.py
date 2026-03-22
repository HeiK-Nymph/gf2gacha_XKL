from pathlib import Path
import sys
from mitmproxy import options
from mitmproxy.tools.dump import DumpMaster
import asyncio
import socket
from winproxy import ProxySetting

# 全局变量：保存实际使用的端口号
actual_port = None


def load_addons():
    """加载addons目录下的addons.py"""
    addons_dir = Path(__file__).parent / 'addons'
    sys.path.insert(0, str(addons_dir))

    import addons
    return addons.addons

p = ProxySetting()

def set_proxy(ip, port):
    """设置代理"""
    p.enable = True
    p.server = f'{ip}:{port}'
    p.registry_write()

def close_proxy():
    """关闭代理"""
    p.enable = False
    p.registry_write()


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

    set_proxy('127.0.0.1', port)

    # 确保证书存在，不存在则自动生成
    from backend.cert_generator import ensure_ca_certificate, generate_user_ca_certificate
    cert_dir, is_new = ensure_ca_certificate()
    if is_new:
        cert_dir = generate_user_ca_certificate()

    # 配置选项
    opts = options.Options(
        listen_port=port,
        ssl_insecure=True,
        confdir=str(cert_dir)  # 使用项目专属证书目录
    )

    # 创建DumpMaster对象
    master = DumpMaster(opts, with_termlog=False)

    # 加载addons
    for addon in load_addons():
        master.addons.add(addon)

    print(f"[OK] mitmproxy启动成功！监听端口: {port}")
    print("[INFO] 按 Ctrl+C 停止代理")

    # 启动代理
    try:
        await master.run()
    except KeyboardInterrupt:
        print("\n[INFO] 正在停止代理...")
        master.shutdown()
    finally:
        close_proxy()

    return port

if __name__ == '__main__':
    asyncio.run(run_proxy(8080))