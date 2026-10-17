"""用真实 WebView 和 html2canvas 检查明细布局；仅使用本地合成记录。"""
import base64
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def child():
    import webview
    import main
    from backend import icon_cache
    from PIL import Image

    output = ROOT / 'build'
    window = webview.create_window('Layout regression', (output / 'gacha-layout/test/gacha-layout.html').as_uri(),
                                   width=1200, height=960, hidden=True)
    failures = []

    def verify():
        try:
            deadline = time.monotonic() + 15
            while not window.evaluate_js('window.fixtureReady === true'):
                assert time.monotonic() < deadline, 'fixture did not load'
                time.sleep(.1)
            time.sleep(.3)  # 等待故意损坏的图片触发兜底。
            checks = window.evaluate_js("""(() => {
              const checks = [];
              const check = (name, passed) => checks.push({name, passed});
              const screen = document.querySelector('.fixture-screen');
              for (const pool of screen.querySelectorAll('.fixture-pool')) {
                const rows = [...pool.querySelectorAll('.ssr-item')];
                const bars = rows.map(row => row.querySelector('.draw-bar').getBoundingClientRect());
                check(pool.dataset.pool + ': all bars aligned', bars.length === 6 && bars.every(bar => Math.abs(bar.x - bars[0].x) < .2 && Math.abs(bar.width - bars[0].width) < .2));
                check(pool.dataset.pool + ': costs preserved', rows.slice(1).map(row => row.querySelector('.draw-cost').textContent).join() === '29,30,59,60,80');
                check(pool.dataset.pool + ': thresholds', rows.slice(1).map(row => ['tone-green','tone-yellow','tone-red'].find(tone => row.classList.contains(tone))).join() === 'tone-green,tone-yellow,tone-yellow,tone-red,tone-red');
                check(pool.dataset.pool + ': full bar at 80', Math.abs(rows[5].querySelector('.bar-fill').getBoundingClientRect().width - bars[5].width) < .2);
                check(pool.dataset.pool + ': gold pity', rows[0].classList.contains('tone-gold'));
                const grid = pool.querySelector('.ssr-grid').getBoundingClientRect();
                check(pool.dataset.pool + ': top grid stays inside card', [...pool.querySelectorAll('.ssr-grid-avatar')].every(el => el.getBoundingClientRect().right <= grid.right));
              }
              const weapon = screen.querySelector('[data-pool="weapon"]');
              check('overview weapons use images', !!weapon.querySelector('.ssr-grid img[data-requested-src*="/weapon/"]') && !weapon.querySelector('.weapon-name'));
              check('overview failed weapon uses 武', [...weapon.querySelectorAll('.ssr-grid .grid-avatar-fallback')].some(el => el.textContent === '武'));
              check('raw data feature removed', !document.querySelector('.raw-data-container') && ![...document.querySelectorAll('button')].some(el => el.textContent.includes('原始数据')));
              check('correct stripe slope', getComputedStyle(weapon.querySelector('.bar-fill')).backgroundImage.includes('45deg'));
              check('weapon image directory', !!weapon.querySelector('.record-avatar img[data-requested-src*="/weapon/"]'));
              check('failed weapon uses 武', [...weapon.querySelectorAll('.avatar-fallback')].some(el => el.textContent === '武'));
              const long = [...weapon.querySelectorAll('.ssr-name')].find(el => el.textContent === window.layoutFixture.longName);
              check('desktop name ellipsis and full title', long.scrollWidth > long.clientWidth && long.title === long.textContent && getComputedStyle(long).whiteSpace === 'nowrap');
              check('desktop stripes animate', (getComputedStyle(weapon.querySelector('.bar-fill')).animationName.startsWith('stripe-move') || matchMedia('(prefers-reduced-motion: reduce)').matches));
              const shared = document.querySelector('.screenshot-container [data-pool="weapon"]');
              const sharedName = [...shared.querySelectorAll('.ssr-name')].find(el => el.textContent === window.layoutFixture.longName);
              check('share name wraps fully', getComputedStyle(sharedName).whiteSpace === 'normal' && sharedName.clientHeight > 30 && sharedName.scrollWidth <= sharedName.clientWidth);
              check('share stripes static', getComputedStyle(shared.querySelector('.bar-fill')).animationName === 'none');
              for (const pool of document.querySelectorAll('.screenshot-container .fixture-pool')) {
                pool.style.width = '280px';
                const row = pool.querySelector('.ssr-item');
                check(pool.dataset.pool + ': narrow share row fits', row.querySelector('.ssr-name').getBoundingClientRect().right <= pool.getBoundingClientRect().right && row.querySelector('.draw-bar').getBoundingClientRect().width > 50);
                pool.style.width = '';
              }
              return checks;
            })()""")
            for check in checks:
                assert check['passed'], check['name']
            print(f'PASS {len(checks)} layout/threshold/image/name/animation checks')

            # 空池和超80抽垫抽仍不产生错行或越界。
            window.evaluate_js("window.savedWeapon = window.layoutFixture.records.gacha.weapon_pool; window.layoutFixture.records.gacha.weapon_pool = []")
            assert window.evaluate_js("document.querySelectorAll('.fixture-screen [data-pool=weapon] .ssr-item').length") == 0
            window.evaluate_js("window.layoutFixture.records.gacha.weapon_pool = [{data:{list:Array.from({length:81},(_,i)=>({item:999,time:i,pool_id:1}))}}]")
            assert window.evaluate_js("document.querySelector('.fixture-screen [data-pool=weapon] .bar-fill').style.width") == '100%'
            window.evaluate_js("window.layoutFixture.records.gacha.weapon_pool = window.savedWeapon")

            # 使用真正的分享后端、html2canvas、PNG校验；拦截写剪贴板的 PowerShell。
            with patch.object(main.GachaApp, '_cleanup_old_updater'):
                app = main.GachaApp()
            app.window = window
            target = output / 'gacha-layout-share.png'

            def capture_clipboard(command, **kwargs):
                path = re.search(r'FromFile\("([^"]+)"\)', command[-1]).group(1)
                shutil.copyfile(path, target)
                return types.SimpleNamespace(returncode=0, stderr='')

            with patch.object(main.subprocess, 'run', side_effect=capture_clipboard):
                result = app.copy_image_to_clipboard()
                assert result['status'] == 'success', result
                # 仅覆写 getter 模拟缓存下载失败，不产生网络请求。
                window.evaluate_js("Object.defineProperty(document.querySelector('.screenshot-container .record-avatar img'), 'src', {get: () => 'https://fixture.invalid/icon.png', configurable:true})")
                with patch.object(icon_cache, 'get_data_uri', return_value=None):
                    target = output / 'gacha-layout-share-fallback.png'
                    result = app.copy_image_to_clipboard()
                    assert result['status'] == 'success', result
            with Image.open(output / 'gacha-layout-share.png') as image:
                colors = image.convert('RGB').getcolors(image.width * image.height)
                colors = {color: count for count, color in colors}
                for color in [(0,176,80),(146,208,80),(217,169,60),(239,201,100)]:
                    assert colors.get(color, 0) > 50, ('missing stripe color', color)
                image.resize((1000, round(image.height * 1000 / image.width))).save(output / 'gacha-layout-preview.png')
            print('PASS empty pool, 81 pity clamp, actual sharing, image-download fallback, rendered stripe colors')
        except Exception as exc:
            failures.append(str(exc))
        finally:
            window.destroy()

    webview.start(verify)
    assert not failures, failures


if __name__ == '__main__':
    if '--child' in sys.argv:
        child()
    else:
        subprocess.run([sys.executable, __file__, '--child'], cwd=ROOT, timeout=60, check=True)
