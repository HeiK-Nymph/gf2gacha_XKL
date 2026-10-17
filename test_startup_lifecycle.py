"""启动/退出回归：不创建窗口、不联网、不修改系统代理。"""
import asyncio
import threading
import time
import types
import tempfile
import unittest
from unittest.mock import patch

import main
from backend import proxy


class StartupTests(unittest.TestCase):
    def setUp(self):
        with patch.object(main.GachaApp, '_cleanup_old_updater'):
            self.app = main.GachaApp()

    def test_bridge_exposes_methods_without_traversing_native_window(self):
        import webview.util as util
        touched = []

        class Native:
            @property
            def dangerous(self):
                touched.append(True)
                return None

        class Flag:
            def set(self):
                pass

        window = types.SimpleNamespace(
            native=Native(), _expose_lock=threading.Lock(), _functions={},
            events=types.SimpleNamespace(before_load=Flag(), loaded=Flag(), _pywebviewready=Flag()),
            run_js=lambda script: None,
        )
        self.app.window = window
        window._js_api = self.app._create_js_api()
        with patch.object(util, 'load_js_files', return_value=('', '%(functions)s')):
            util.inject_pywebview('edgechromium', window)
            for thread in threading.enumerate():
                if 'generate_js_object' in thread.name:
                    thread.join(1)
        self.assertFalse(touched)
        self.assertTrue(callable(window._js_api.get_startup_ssr_data))
        self.assertFalse(hasattr(window._js_api, 'window'))

    def test_slow_parser_does_not_block_startup_and_refresh_is_single_flight(self):
        release = threading.Event()
        entered = threading.Event()
        fresh = {'version': 'fresh', 'SSR_character': {'1': 'test'}}

        def slow():
            entered.set()
            release.wait(2)
            return fresh, 'local-proto'

        with patch.object(self.app, '_load_ssr_data_impl', side_effect=slow) as load:
            try:
                started = time.monotonic()
                initial = self.app.get_startup_ssr_data()
                self.assertLess(time.monotonic() - started, .5)
                self.assertEqual(initial['source'], 'local-json')
                self.assertTrue(initial['data']['SSR_character'])
                self.assertTrue(entered.wait(.5))
                self.app.get_startup_ssr_data()
                self.assertEqual(load.call_count, 1)
            finally:
                release.set()
                self.app._ssr_thread.join(2)
        result = self.app.get_startup_ssr_data()
        self.assertEqual(result['source'], 'local-proto')
        self.assertFalse(result['refreshing'])

    def test_remote_ssr_bypasses_environment_proxy(self):
        with patch.object(main.requests, 'Session') as session:
            session.return_value.__enter__.return_value = session.return_value
            session.return_value.get.return_value.status_code = 200
            session.return_value.get.return_value.json.return_value = {'SSR_character': {'1': 'x'}}
            self.app._fetch_remote_ssr()
            self.assertFalse(session.return_value.trust_env)

    def test_close_signals_stop_even_when_proxy_cleanup_raises(self):
        with patch.object(proxy, 'stop_proxy', side_effect=RuntimeError('cleanup')), \
             patch('backend.capture.clear_capture', return_value={'status': 'success'}):
            self.app.on_closed()
        self.assertTrue(self.app._closing.is_set())
        self.assertFalse(self.app.start_proxy())

    def test_close_during_proxy_startup_never_enables_system_proxy(self):
        closing = threading.Event()
        closing.set()
        with patch.object(proxy, 'set_proxy') as enable, patch.object(proxy, 'close_proxy'):
            asyncio.run(proxy.run_proxy(stop_event=closing))
        enable.assert_not_called()

    def test_start_update_launches_updater_from_install_root(self):
        from pathlib import Path
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'updater.exe').touch()
            self.app.window = types.SimpleNamespace(destroy=Mock())
            with patch.object(main, '_app_root', return_value=root), \
                 patch.object(main, '_write_update_state'), \
                 patch.object(main.subprocess, 'Popen') as launch, \
                 patch.object(proxy, 'close_proxy'):
                result = self.app.start_update()
            self.assertEqual(result['status'], 'success', result)
            self.assertEqual(launch.call_args.kwargs['cwd'], str(root))
            self.app.window.destroy.assert_called_once()

    def test_proxy_only_enables_after_listening_and_stops_on_close(self):
        self._exercise_proxy(stop_before_ready=False)

    def test_proxy_close_before_running_hook_cannot_reenable_proxy(self):
        self._exercise_proxy(stop_before_ready=True)

    def _exercise_proxy(self, stop_before_ready):
        closing = threading.Event()
        events = []

        class Addons:
            def add(self, addon):
                self.lifecycle = addon

        class Master:
            def __init__(self, *args, **kwargs):
                self.addons = Addons()
                self.stopped = asyncio.Event()

            async def run(self):
                events.append('listening')
                if stop_before_ready:
                    closing.set()
                self.addons.lifecycle.running()
                proxy.stop_proxy()
                await asyncio.wait_for(self.stopped.wait(), 1)

            def shutdown(self):
                events.append('shutdown')
                self.stopped.set()

        with patch.object(proxy, 'DumpMaster', Master), \
             patch.object(proxy.options, 'Options'), \
             patch.object(proxy, 'find_available_port', return_value=8080), \
             patch.object(proxy, '_can_connect', return_value=True), \
             patch.object(proxy, 'load_addons', return_value=[]), \
             patch.object(proxy, 'set_proxy', side_effect=lambda *args: events.append('enable')) as enable, \
             patch.object(proxy, 'close_proxy'), \
             patch('backend.cert_generator.ensure_ca_certificate', return_value=('.', False)):
            asyncio.run(proxy.run_proxy(stop_event=closing))
        if stop_before_ready:
            enable.assert_not_called()
        else:
            self.assertLess(events.index('listening'), events.index('enable'))
        self.assertIn('shutdown', events)
        self.assertFalse(proxy.get_proxy_status()['ready'])
        self.assertIsNone(proxy._active_master)

    def test_proxy_restores_original_settings_once(self):
        with patch.object(proxy, 'ProxySetting') as previous, patch.object(proxy, 'p'), \
             patch.object(proxy, '_previous_proxy', None):
            proxy.close_proxy()
            previous.return_value.registry_write.assert_not_called()
            proxy.set_proxy('127.0.0.1', 8080)
            proxy.set_proxy('127.0.0.1', 8080)
            proxy.close_proxy()
            proxy.close_proxy()
            previous.return_value.registry_read.assert_called_once()
            previous.return_value.registry_write.assert_called_once()

    def test_first_run_certificate_exports_pkcs12(self):
        from pathlib import Path
        from backend import cert_generator
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            cert_generator, '__file__', str(Path(tmp) / 'backend' / 'cert_generator.py')
        ):
            directory = cert_generator.generate_user_ca_certificate()
            self.assertTrue((directory / 'mitmproxy-ca-cert.p12').is_file())

    def test_real_mitmproxy_listener_can_start_and_stop_without_registry_changes(self):
        async def exercise():
            closing = threading.Event()
            with tempfile.TemporaryDirectory() as tmp, \
                 patch('backend.cert_generator.ensure_ca_certificate', return_value=(tmp, False)), \
                 patch.object(proxy, 'load_addons', return_value=[]), \
                 patch.object(proxy, 'set_proxy') as enable, patch.object(proxy, 'close_proxy'):
                task = asyncio.create_task(proxy.run_proxy(stop_event=closing))
                try:
                    deadline = time.monotonic() + 10
                    while not proxy.get_proxy_status()['ready']:
                        if task.done():
                            await task
                            self.fail('代理未进入 ready 状态')
                        if time.monotonic() > deadline:
                            self.fail('代理启动超时')
                        await asyncio.sleep(.05)
                    enable.assert_called_once()
                    proxy.stop_proxy()
                    await asyncio.wait_for(task, 3)
                    self.assertTrue(closing.is_set())
                finally:
                    if not task.done():
                        proxy.stop_proxy()
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
        asyncio.run(exercise())


if __name__ == '__main__':
    unittest.main()
