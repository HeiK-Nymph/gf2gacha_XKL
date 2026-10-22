"""系统代理：allow_hosts 范围、注册表快照恢复、看门狗顺序。"""
import os
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from backend import proxy, proxy_watchdog


def _new_key_path() -> str:
    return f"Software\\gf2gacha_XKL_test_{uuid.uuid4().hex}"


class TargetedProxyTests(unittest.TestCase):
    def test_allow_hosts_matches_only_game_record_host(self):
        import re

        patterns = proxy._allow_host_patterns()
        target = "gf2-gacha-record.sunborngame.com:443"
        others = [
            "gf2-zoneinfo.sunborngame.com:443",
            "example.com:443",
            "sunborngame.com.evil.test:443",
        ]
        self.assertTrue(any(re.search(p, target, re.IGNORECASE) for p in patterns))
        for other in others:
            self.assertFalse(any(re.search(p, other, re.IGNORECASE) for p in patterns), other)

    def test_options_set_allow_hosts(self):
        from backend.cert_generator import ensure_ca_certificate

        cert_dir, _ = ensure_ca_certificate()
        opts = proxy._make_options(18099, cert_dir)
        self.assertTrue(opts.allow_hosts)

    def test_registry_snapshot_restores_previous_manual_proxy(self):
        key_path = _new_key_path()
        winreg = proxy_watchdog.winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "corp.proxy:3128")
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "*.corp.example")
            winreg.SetValueEx(key, "AutoConfigURL", 0, winreg.REG_SZ, "https://corp.example/proxy.pac")
        try:
            with patch.object(proxy_watchdog, "INTERNET_SETTINGS_KEY", key_path), \
                 patch.object(proxy_watchdog, "notify_proxy_change"):
                snapshot = proxy_watchdog.capture_proxy_snapshot("127.0.0.1:8080")
                proxy_watchdog.apply_manual_proxy("127.0.0.1:8080")
                self.assertEqual(proxy_watchdog.read_manual_proxy(), (1, "127.0.0.1:8080"))
                self.assertFalse(proxy_watchdog.read_auto_config_url()[0])
                self.assertTrue(proxy_watchdog.restore_proxy_snapshot(snapshot))
                self.assertEqual(proxy_watchdog.read_manual_proxy(), (1, "corp.proxy:3128"))
                self.assertEqual(proxy_watchdog.read_auto_config_url()[1], "https://corp.example/proxy.pac")
        finally:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)

    def test_registry_restore_does_not_overwrite_user_change(self):
        key_path = _new_key_path()
        winreg = proxy_watchdog.winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS):
            pass
        try:
            with patch.object(proxy_watchdog, "INTERNET_SETTINGS_KEY", key_path), \
                 patch.object(proxy_watchdog, "notify_proxy_change"):
                snapshot = proxy_watchdog.capture_proxy_snapshot("127.0.0.1:8080")
                proxy_watchdog.apply_manual_proxy("127.0.0.1:8080")
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "user.proxy:8080")
                self.assertFalse(proxy_watchdog.restore_proxy_snapshot(snapshot))
                self.assertEqual(proxy_watchdog.read_manual_proxy(), (1, "user.proxy:8080"))
        finally:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)

    def test_missing_certificate_never_touches_registry(self):
        old_lease = proxy._proxy_lease
        try:
            proxy._proxy_lease = None
            with patch.object(proxy, "_certificate_is_trusted", return_value=False), \
                 patch.object(proxy, "_recover_stale_proxy_state"), \
                 patch.object(proxy, "apply_manual_proxy") as apply_proxy:
                self.assertFalse(proxy.set_proxy("127.0.0.1", 8080))
            apply_proxy.assert_not_called()
            self.assertIn("证书", proxy.get_proxy_status()["error"])
        finally:
            proxy._proxy_lease = old_lease

    def test_watchdog_is_started_before_registry_is_modified(self):
        events = []
        old_lease = proxy._proxy_lease
        try:
            proxy._proxy_lease = None
            with tempfile.TemporaryDirectory() as tmp, \
                 patch.object(proxy, "_certificate_is_trusted", return_value=True), \
                 patch.object(proxy, "_runtime_dir", return_value=Path(tmp)), \
                 patch.object(proxy, "_recover_stale_proxy_state"), \
                 patch.object(proxy, "capture_proxy_snapshot", return_value={"server": "127.0.0.1:8080", "previous": {}}), \
                 patch.object(proxy, "write_snapshot"), \
                 patch.object(proxy, "_start_watchdog", side_effect=lambda *a: events.append("watchdog") or True), \
                 patch.object(proxy, "apply_manual_proxy", side_effect=lambda *a: events.append("registry")), \
                 patch.object(proxy, "load_snapshot", return_value={"server": "127.0.0.1:8080", "previous": {}}), \
                 patch.object(proxy, "restore_proxy_snapshot", return_value=True), \
                 patch.object(proxy, "proxy_owned_by_us", return_value=False), \
                 patch.object(proxy, "_stop_watchdog"), \
                 patch.object(proxy, "_cleanup_lease_files"):
                self.assertTrue(proxy.set_proxy("127.0.0.1", 8080))
                self.assertLess(events.index("watchdog"), events.index("registry"))
                proxy.close_proxy()
                self.assertIsNone(proxy._proxy_lease)
        finally:
            proxy._proxy_lease = old_lease

    def test_stale_snapshot_is_restored_before_new_lease(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(proxy, "_runtime_dir", return_value=Path(tmp)), \
             patch.object(proxy, "load_snapshot", return_value={"server": "127.0.0.1:8080", "previous": {}}), \
             patch.object(proxy, "proxy_owned_by_us", return_value=True), \
             patch.object(proxy, "restore_proxy_snapshot", return_value=True) as restore:
            snapshot_path = Path(tmp) / "gf2-proxy-1.json"
            snapshot_path.write_text("{}", encoding="utf-8")
            proxy._recover_stale_proxy_state()
            restore.assert_called_once()
            self.assertFalse(snapshot_path.exists())

    def test_repair_stale_legacy_proxy_only_disables_dead_local_endpoint(self):
        key_path = _new_key_path()
        winreg = proxy_watchdog.winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "127.0.0.1:8179")
        try:
            with patch.object(proxy_watchdog, "INTERNET_SETTINGS_KEY", key_path), \
                 patch.object(proxy_watchdog, "_endpoint_is_listening", return_value=False), \
                 patch.object(proxy_watchdog, "notify_proxy_change"):
                self.assertTrue(proxy_watchdog.repair_stale_local_proxy())
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                self.assertEqual(winreg.QueryValueEx(key, "ProxyEnable")[0], 0)
        finally:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)

    def test_watchdog_process_restores_registry_after_parent_exit(self):
        key_path = _new_key_path()
        winreg = proxy_watchdog.winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "corp.proxy:3128")
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "*.corp.example")
        watcher = None
        fake_parent = None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with patch.object(proxy_watchdog, "INTERNET_SETTINGS_KEY", key_path), \
                     patch.object(proxy_watchdog, "notify_proxy_change"):
                    snapshot = proxy_watchdog.capture_proxy_snapshot("127.0.0.1:8080")
                    snapshot_path = Path(tmp) / "snapshot.json"
                    ready_path = Path(tmp) / "watchdog.ready"
                    stop_path = Path(tmp) / "watchdog.stop"
                    proxy_watchdog.write_snapshot(snapshot_path, snapshot)
                    proxy_watchdog.apply_manual_proxy("127.0.0.1:8080")

                fake_parent = subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(1.2)"],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                env = os.environ.copy()
                env["GF2XKL_PROXY_REGISTRY_KEY"] = key_path
                main_path = Path(__file__).resolve().parent / "main.py"
                watcher = subprocess.Popen(
                    [
                        sys.executable,
                        str(main_path),
                        "--proxy-watchdog",
                        str(fake_parent.pid),
                        str(snapshot_path),
                        str(ready_path),
                        str(stop_path),
                    ],
                    cwd=str(main_path.parent),
                    env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                deadline = time.monotonic() + 8
                while not ready_path.exists() and time.monotonic() < deadline:
                    if watcher.poll() is not None:
                        self.fail(f"watchdog exited early: {watcher.returncode}")
                    time.sleep(0.05)
                self.assertTrue(ready_path.exists())

                fake_parent.wait(timeout=5)
                watcher.wait(timeout=5)
                with patch.object(proxy_watchdog, "INTERNET_SETTINGS_KEY", key_path):
                    self.assertEqual(proxy_watchdog.read_manual_proxy(), (1, "corp.proxy:3128"))
        finally:
            for process in (watcher, fake_parent):
                if process is not None and process.poll() is None:
                    process.terminate()
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)


if __name__ == "__main__":
    unittest.main()
