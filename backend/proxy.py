from pathlib import Path
import sys
from mitmproxy import options
from mitmproxy.tools.dump import DumpMaster
import asyncio
from winproxy import ProxySetting


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


async def run_proxy(port=8080):
    """启动代理服务器"""

    set_proxy('127.0.0.1', port)

    # 配置选项
    opts = options.Options(
        listen_port=port,
        ssl_insecure=True
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

if __name__ == '__main__':
    asyncio.run(run_proxy(8080))