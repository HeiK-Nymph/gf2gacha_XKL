"""验证裁剪后的真实 EXE：在临时副本中启动、等待代理与数据加载、关闭。

python tools/verify_frozen_build.py dist/slim/gf2gacha_XKL
"""
import ctypes
from ctypes import wintypes
import winreg
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.proxy_watchdog import (
    _delete_value,
    _set_value,
    _settings_key,
    notify_proxy_change,
    read_proxy_values,
)


def find_window(pid):
    user32 = ctypes.windll.user32
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def visit(hwnd, _):
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value == pid:
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, len(title))
            if title.value == '夏克里助手':
                found.append(hwnd)
        return True

    user32.EnumWindows(visit, 0)
    return found[0] if found else None


def verify(source):
    source = Path(source).resolve()
    assert (source / 'gf2gacha_XKL.exe').is_file(), source
    original_values = read_proxy_values()
    process = None
    temporary = tempfile.TemporaryDirectory(prefix='xkl_frozen_')
    try:
        tmp = temporary.name
        root = Path(tmp).resolve()
        assert root.parent == Path(tempfile.gettempdir()).resolve()
        bundle = root / 'app'
        shutil.copytree(source, bundle)
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = 0
        process = subprocess.Popen([str(bundle / 'gf2gacha_XKL.exe')], cwd=bundle, startupinfo=info)
        log_path = bundle / '_internal/logs/app.log'
        deadline = time.monotonic() + 35
        hwnd = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'EXE exited before ready: {process.returncode}')
            hwnd = find_window(process.pid)
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
            log = log_path.read_text(encoding='utf-8', errors='replace') if log_path.exists() else ''
            proxy_ready = '[OK] mitmproxy 已就绪' in log or '[WARN] mitmproxy 已就绪' in log
            if '[STARTUP] 五星表刷新结束' in log and proxy_ready and hwnd:
                assert 'ModuleNotFoundError' not in log and '[ERROR]' not in log, log
                break
            time.sleep(.2)
        else:
            raise RuntimeError(f'EXE startup timed out. Log:\n{log}')
        ctypes.windll.user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
        process.wait(timeout=10)
        assert process.returncode == 0, process.returncode
        after_values = read_proxy_values()
        assert after_values == original_values
        print('PASS frozen EXE: WebView + proxy + SSR startup + clean exit + proxy restoration')
        process = None
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _settings_key(), 0, winreg.KEY_SET_VALUE) as key:
            for name, item in original_values.items():
                if item.get("exists"):
                    _set_value(key, name, item.get("value"), int(item.get("type") or winreg.REG_SZ))
                else:
                    _delete_value(key, name)
        notify_proxy_change()
        temporary.cleanup()


if __name__ == '__main__':
    verify(sys.argv[1])
