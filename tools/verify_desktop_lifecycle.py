"""真实 Windows WebView 回归；隔离网络、系统代理、证书和用户记录。

python tools/verify_desktop_lifecycle.py
"""
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def child(scenario):
    import main
    import webview
    from backend import capture

    with patch.object(main.GachaApp, '_cleanup_old_updater'):
        app = main.GachaApp()
    blocked = threading.Event()
    result = []

    def slow_parser():
        blocked.wait(.5 if scenario == 'fresh-data' else 60)
        return {'SSR_character': {'1': 'test'}}, 'local-proto'

    app._load_ssr_data_impl = slow_parser
    app.get_record_list = lambda: {'status': 'success', 'data': []}
    app.get_capture_status = lambda: {'status': 'success', 'proxy': {}, 'capture': {}}
    app.get_update_status = lambda: {'needs_attention': False}
    app.mark_update_ok = lambda: {'status': 'success'}
    original_create = webview.create_window
    original_start = webview.start

    def create(*args, **kwargs):
        return original_create(*args, **kwargs, hidden=True)

    def verify():
        try:
            if scenario in ('loading', 'fresh-data'):
                if not app.window.events._pywebviewready.wait(10):
                    raise AssertionError('bridge not ready')
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if app.window.evaluate_js("document.querySelector('.loading-overlay') === null"):
                        result.append('PASS: UI loaded while parser blocked')
                        break
                    time.sleep(.1)
                else:
                    raise AssertionError('loading overlay never cleared')
                if scenario == 'fresh-data':
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        # 2026-10 UI 改版后 toast 是自研组件（src/ui/AppToastHost.vue）：
                        # .app-toast + 类型类名，文案在 .app-toast-text 里
                        notice = app.window.evaluate_js("""Array.from(document.querySelectorAll('.app-toast')).map(
                            element => ({
                                text: (element.querySelector('.app-toast-text') || {}).textContent || '',
                                success: element.classList.contains('success')
                            })
                        )""")
                        if notice:
                            assert len(notice) == 1, notice
                            assert notice[0]['success'], notice
                            assert '正在使用最新五星数据' in notice[0]['text'], notice
                            result.append('PASS: exactly one green latest-data notification')
                            break
                        time.sleep(.1)
                    else:
                        raise AssertionError('latest-data notification missing')
            else:
                if not app.window.events.before_load.wait(10):
                    raise AssertionError('page did not begin loading')
                result.append('PASS: close during bridge initialization')
        except Exception as exc:
            result.append(f'FAIL: {exc}')
        finally:
            app.window.destroy()

    # Capture 的读写均替换为无敏感数据的内存结果。
    info = {'path': 'isolated', 'exists': False, 'size': 0, 'replayable': False, 'captured_at': None}
    with patch.object(main, '_init_logging'), \
         patch.object(app, '_check_and_generate_certificate'), \
         patch.object(app, 'start_proxy', return_value=False), \
         patch.object(capture, 'describe_capture', return_value=info), \
         patch.object(capture, 'clear_capture', return_value={'status': 'success'}), \
         patch.object(webview, 'create_window', side_effect=create), \
         patch.object(webview, 'start', side_effect=lambda: original_start(verify)):
        app.run()
    assert app._closing.is_set()
    assert result and all(item.startswith('PASS') for item in result), result
    print('\n'.join(result), flush=True)
    # 故意不放行 daemon 解析线程，确认它不会阻止进程退出。


if __name__ == '__main__':
    if len(sys.argv) > 1:
        child(sys.argv[1])
    else:
        for scenario in ('loading', 'early-close', 'fresh-data'):
            started = time.monotonic()
            run = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), scenario],
                cwd=ROOT, timeout=30, capture_output=True, text=True, errors='replace',
            )
            print(run.stdout)
            if run.returncode:
                print(run.stderr)
                raise SystemExit(run.returncode)
            print(f'{scenario}: process exited in {time.monotonic() - started:.2f}s')
