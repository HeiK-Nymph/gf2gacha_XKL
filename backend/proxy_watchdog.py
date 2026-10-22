"""Windows 系统代理的注册表操作与崩溃看门狗。

设计要点：
* 只修改 HKCU 下的 Internet Settings 下的 4 个值，并在改动前完整快照；
* 快照放在独立进程能读到的文件里，主进程被强杀时由看门狗恢复；
* 本模块刻意只用标准库：看门狗进程会在导入 webview / mitmproxy 之前进入这里。
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import socket
import time
from typing import Any

if os.name == "nt":  # pragma: no cover - 只在 Windows 上执行
    import winreg
else:  # pragma: no cover - 便于在非 Windows 环境导入和测试
    winreg = None


INTERNET_SETTINGS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
PROXY_ENABLE = "ProxyEnable"
PROXY_SERVER = "ProxyServer"
PROXY_OVERRIDE = "ProxyOverride"
AUTO_CONFIG_URL = "AutoConfigURL"
SNAPSHOT_SCHEMA = 2

# 启用本工具代理期间的绕过列表：保留局域网/本机直连，避免影响本地服务。
ACTIVE_PROXY_OVERRIDE = "<local>"

INTERNET_OPTION_REFRESH = 37
INTERNET_OPTION_SETTINGS_CHANGED = 39

WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
SYNCHRONIZE = 0x00100000


class ProxySettingsError(RuntimeError):
    """注册表代理设置无法安全读取或恢复。"""


def _require_windows() -> None:
    if os.name != "nt" or winreg is None:
        raise ProxySettingsError("系统代理仅支持 Windows")


def _settings_key() -> str:
    """测试/排障时可覆盖注册表键，生产环境始终使用 IE Internet Settings。"""
    return os.environ.get("GF2XKL_PROXY_REGISTRY_KEY", INTERNET_SETTINGS_KEY)


def _read_value(key, name: str) -> tuple[bool, Any, int]:
    try:
        value, value_type = winreg.QueryValueEx(key, name)
        return True, value, int(value_type)
    except FileNotFoundError:
        return False, None, 0


def read_proxy_values() -> dict[str, dict[str, Any]]:
    """读取本工具会改动的 4 个注册表值。"""
    _require_windows()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _settings_key(), 0, winreg.KEY_READ) as key:
            return {
                name: dict(zip(("exists", "value", "type"), _read_value(key, name)))
                for name in (PROXY_ENABLE, PROXY_SERVER, PROXY_OVERRIDE, AUTO_CONFIG_URL)
            }
    except OSError as exc:
        raise ProxySettingsError(f"读取系统代理设置失败: {exc}") from exc


def read_auto_config_url() -> tuple[bool, str, int]:
    """兼容旧调用：返回 (是否存在, 值, 注册表类型)。"""
    _require_windows()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _settings_key(), 0, winreg.KEY_READ) as key:
            exists, value, value_type = _read_value(key, AUTO_CONFIG_URL)
            return exists, str(value or ""), int(value_type)
    except OSError as exc:
        raise ProxySettingsError(f"读取 AutoConfigURL 失败: {exc}") from exc


def read_manual_proxy() -> tuple[int, str]:
    """返回 (ProxyEnable, ProxyServer)。"""
    _require_windows()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _settings_key(), 0, winreg.KEY_READ) as key:
            _, enabled, _ = _read_value(key, PROXY_ENABLE)
            _, server, _ = _read_value(key, PROXY_SERVER)
            return int(enabled or 0), str(server or "")
    except OSError as exc:
        raise ProxySettingsError(f"读取 ProxyEnable/ProxyServer 失败: {exc}") from exc


def notify_proxy_change() -> None:
    """通知 WinINET 立即重新读取代理设置。"""
    try:
        wininet = ctypes.WinDLL("wininet", use_last_error=True)
        wininet.InternetSetOptionW(None, INTERNET_OPTION_SETTINGS_CHANGED, None, 0)
        wininet.InternetSetOptionW(None, INTERNET_OPTION_REFRESH, None, 0)
    except Exception:
        pass


def _endpoint_is_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def repair_stale_local_proxy() -> bool:
    """修复旧版强杀后遗留的 127.0.0.1:8080-8179 全局代理。

    只有当前代理服务器全部是旧版端口范围内的本机地址、且都没有进程监听时，
    才关闭 ProxyEnable。正常运行的本地代理或其它端口一律不动。
    """
    _require_windows()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _settings_key(), 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
            exists_enabled, enabled, _ = _read_value(key, PROXY_ENABLE)
            exists_server, server, _ = _read_value(key, PROXY_SERVER)
            if not exists_enabled or not exists_server:
                return False
            if int(enabled or 0) != 1 or not server:
                return False

            ports = []
            for item in str(server).split(";"):
                endpoint = item.split("=", 1)[-1].strip()
                endpoint = endpoint.removeprefix("http://").removeprefix("https://")
                if endpoint.count(":") != 1:
                    return False
                host, port_text = endpoint.rsplit(":", 1)
                if host.lower() not in {"127.0.0.1", "localhost"}:
                    return False
                try:
                    port = int(port_text)
                except ValueError:
                    return False
                if port not in range(8080, 8180):
                    return False
                ports.append(port)

            if not ports or any(_endpoint_is_listening(port) for port in ports):
                return False

            winreg.SetValueEx(key, PROXY_ENABLE, 0, winreg.REG_DWORD, 0)
        notify_proxy_change()
        return True
    except OSError:
        return False


def capture_proxy_snapshot(server: str) -> dict[str, Any]:
    """在修改前保存全部相关代理设置，供退出/崩溃时原样恢复。"""
    return {
        "schema": SNAPSHOT_SCHEMA,
        "created_at": time.time(),
        "server": str(server),
        "previous": read_proxy_values(),
    }


def write_snapshot(path: str | Path, snapshot: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_snapshot(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - 损坏的快照只能放弃
        raise ProxySettingsError(f"读取代理快照失败: {exc}") from exc
    if not isinstance(data, dict) or not data.get("server"):
        raise ProxySettingsError("代理快照缺少 server 字段")
    if not isinstance(data.get("previous"), dict):
        raise ProxySettingsError("代理快照缺少 previous 字段")
    return data


def _set_value(key, name: str, value: Any, value_type: int) -> None:
    winreg.SetValueEx(key, name, 0, value_type, value)


def _delete_value(key, name: str) -> None:
    try:
        winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass


def merge_proxy_override(value: Any) -> str:
    """保留用户原有绕过规则，并确保本机/局域网继续直连。"""
    items = []
    seen = set()
    for part in str(value or "").split(";"):
        item = part.strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            items.append(item)
    if "<local>" not in seen:
        items.append("<local>")
    return ";".join(items)


def apply_manual_proxy(server: str) -> None:
    """把系统代理指向本机 mitmproxy，并清掉 PAC 以免两套配置互相影响。"""
    _require_windows()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _settings_key(), 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
            _, previous_override, _ = _read_value(key, PROXY_OVERRIDE)
            _set_value(key, PROXY_ENABLE, 1, winreg.REG_DWORD)
            _set_value(key, PROXY_SERVER, str(server), winreg.REG_SZ)
            _set_value(key, PROXY_OVERRIDE, merge_proxy_override(previous_override), winreg.REG_SZ)
            _delete_value(key, AUTO_CONFIG_URL)
            enabled, current = read_manual_proxy()
            if enabled != 1 or current != str(server):
                raise ProxySettingsError("ProxyEnable/ProxyServer 未生效（可能被组策略覆盖）")
    except OSError as exc:
        raise ProxySettingsError(f"写入系统代理设置失败: {exc}") from exc
    notify_proxy_change()


def proxy_owned_by_us(snapshot: dict[str, Any]) -> bool:
    """当前代理是否仍指向本工具（用户中途改过就不该覆盖）。"""
    try:
        enabled, server = read_manual_proxy()
    except Exception:
        return False
    return enabled == 1 and server == str(snapshot.get("server") or "")


def restore_proxy_snapshot(snapshot: dict[str, Any]) -> bool:
    """把 4 个代理相关值恢复到快照；用户已改动时不覆盖。"""
    _require_windows()
    if not proxy_owned_by_us(snapshot):
        return False

    previous = snapshot.get("previous") or {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _settings_key(), 0, winreg.KEY_SET_VALUE) as key:
            for name in (PROXY_ENABLE, PROXY_SERVER, PROXY_OVERRIDE, AUTO_CONFIG_URL):
                item = previous.get(name) or {}
                if item.get("exists"):
                    value_type = int(item.get("type") or winreg.REG_SZ)
                    _set_value(key, name, item.get("value"), value_type)
                else:
                    _delete_value(key, name)
    except OSError as exc:
        raise ProxySettingsError(f"恢复系统代理设置失败: {exc}") from exc
    notify_proxy_change()
    return True


def _cleanup_files(snapshot: dict[str, Any], *paths: str | Path) -> None:
    for candidate in paths:
        if not candidate:
            continue
        try:
            Path(candidate).unlink(missing_ok=True)
        except OSError:
            pass


def _restore_until_released(snapshot: dict[str, Any], snapshot_path: Path, ready_path: Path, stop_path: Path) -> None:
    """恢复失败时继续重试；用户已经自己改过代理则直接放手。"""
    while True:
        try:
            if restore_proxy_snapshot(snapshot):
                _cleanup_files(snapshot, snapshot_path, ready_path, stop_path)
                return
            if not proxy_owned_by_us(snapshot):
                _cleanup_files(snapshot, snapshot_path, ready_path, stop_path)
                return
        except Exception:
            pass
        time.sleep(2)


def run_watchdog(parent_pid: int, snapshot_path: str, ready_path: str, stop_path: str) -> int:
    """等待主进程退出；主进程异常消失时恢复系统代理设置。"""
    _require_windows()
    snapshot = load_snapshot(snapshot_path)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(SYNCHRONIZE, False, int(parent_pid))
    if not handle:
        _restore_until_released(snapshot, Path(snapshot_path), Path(ready_path), Path(stop_path))
        return 0

    try:
        # 句柄已经握住才通知主进程可以改注册表，保证崩溃时一定有人负责恢复。
        Path(ready_path).write_text(str(os.getpid()), encoding="ascii")
        while True:
            if Path(stop_path).exists():
                return 0
            result = kernel32.WaitForSingleObject(handle, 200)
            if result == WAIT_OBJECT_0:
                _restore_until_released(snapshot, Path(snapshot_path), Path(ready_path), Path(stop_path))
                return 0
            if result != WAIT_TIMEOUT:
                return 2
    finally:
        kernel32.CloseHandle(handle)
