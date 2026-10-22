#!/usr/bin/env node
/**
 * PC 版界面截图 harness —— 只用 vite dev server + 独立 profile 的 headless Chrome。
 *
 * 绝不启动 main.py / mitmproxy，也不碰系统代理：
 *   pywebview 的 window.pywebview.api 用 CDP Page.addScriptToEvaluateOnNewDocument
 *   在页面脚本之前注入假实现，mock 不落进 frontend/src。
 *
 * 用法（vite 已在 5175 跑着）：
 *   node tools/site-shots/pc/shoot.mjs
 * 环境变量：CDP_PORT(9222) APP_URL(http://127.0.0.1:5175/) SHOT_ONLY(01|02|03)
 */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..', '..');
const OUT_DIR = path.join(ROOT, 'XKL_site', 'public', 'shots', 'pc');
const RAW_DIR = path.join(HERE, 'raw');

const CDP_PORT = Number(process.env.CDP_PORT || 9222);
const APP_URL = process.env.APP_URL || 'http://127.0.0.1:5175/';
const VIEWPORT = { width: 1440, height: 900, dpr: 2 };
const CHROME =
  process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const log = (...a) => console.log(`[shot]`, ...a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ------------------------------------------------------------------ *
 * 1. mock 脚本：在页面任何脚本之前把 window.pywebview.api 装好
 * ------------------------------------------------------------------ */
const mock = JSON.parse(fs.readFileSync(path.join(HERE, 'mock-data.json'), 'utf8'));

function buildInitScript() {
  const payload = JSON.stringify({
    uid: mock.uid,
    recordList: mock.recordList,
    records: mock.records,
    ssr: mock.ssr,
    version: mock.version,
    status: mock.status,
  });
  // 注意：这里只是字符串，注入到页面执行；不会改动 frontend/src
  return `(() => {
  const D = ${payload};
  const clone = (v) => (v === undefined ? null : JSON.parse(JSON.stringify(v)));
  const ok = (extra) => Object.assign({ status: 'success' }, extra || {});
  const api = {
    get_startup_ssr_data: () => Promise.resolve(ok({ source: 'local-json', data: clone(D.ssr), refreshing: false })),
    get_ssr_data: () => Promise.resolve(ok({ data: clone(D.ssr) })),
    load_ssr_data: () => Promise.resolve(ok({ source: 'local-json', data: clone(D.ssr) })),
    get_record_list: () => Promise.resolve(ok({ msg: '获取记录列表成功', data: clone(D.recordList) })),
    import_record: (id) => Promise.resolve(ok({
      msg: '导入抽卡记录成功',
      data: clone(D.records[id] || D.records[D.uid]),
    })),
    export_record: () => Promise.resolve(ok({ msg: '保存抽卡记录成功' })),
    get_capture_status: () => Promise.resolve(clone(D.status)),
    get_update_status: () => Promise.resolve(ok({ needs_attention: false })),
    mark_update_ok: () => Promise.resolve(ok({})),
    dismiss_update_status: () => Promise.resolve(ok({})),
    get_version_info: () => Promise.resolve(ok({ current_version: D.version, latest_version: D.version, has_update: false, notes: '' })),
    prefetch_share_images: (urls) => Promise.resolve(ok({ msg: '已缓存 ' + ((urls || []).length) + ' 张图标', count: (urls || []).length })),
    copy_image_to_clipboard: () => Promise.resolve(ok({ message: 'mock' })),
    open_log_file: () => Promise.resolve(ok({})),
    open_github: () => Promise.resolve(ok({})),
    install_cert: () => Promise.resolve(ok({ msg: '证书安装成功（mock）' })),
    uninstall_cert: () => Promise.resolve(ok({ msg: '证书卸载成功（mock）' })),
    start_update: () => Promise.resolve(ok({})),
    rollback_update: () => Promise.resolve(ok({})),
    get_gacha: () => Promise.resolve({ status: 'error', code: 'no_capture', msg: 'mock：截图 harness 不重放游戏请求' }),
  };
  window.pywebview = { api };
  Object.defineProperty(window, '__PYWEBVIEW_MOCK__', { value: true, enumerable: false });
  if (!window.html2canvas) window.html2canvas = function () { throw new Error('mock'); };
})();`;
}

/* ------------------------------------------------------------------ *
 * 2. 极简 CDP 客户端（Node 22 自带 WebSocket）
 * ------------------------------------------------------------------ */
class CDP {
  constructor(ws) {
    this.ws = ws;
    this.seq = 0;
    this.pending = new Map();
    this.listeners = new Map();
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? reject(new Error(`${msg.method || 'cdp'}: ${JSON.stringify(msg.error)}`)) : resolve(msg.result);
      } else if (msg.method) {
        for (const fn of this.listeners.get(msg.method) || []) fn(msg.params);
      }
    });
  }
  static async connect(url) {
    const ws = new WebSocket(url);
    await new Promise((resolve, reject) => {
      ws.addEventListener('open', resolve, { once: true });
      ws.addEventListener('error', () => reject(new Error(`WebSocket 连接失败: ${url}`)), { once: true });
    });
    return new CDP(ws);
  }
  send(method, params = {}) {
    const id = ++this.seq;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  on(method, fn) {
    if (!this.listeners.has(method)) this.listeners.set(method, []);
    this.listeners.get(method).push(fn);
  }
  close() {
    try { this.ws.close(); } catch {}
  }
}

async function httpJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} -> HTTP ${r.status}`);
  return r.json();
}

async function launchChrome() {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'dsh-pc-shots-'));
  const args = [
    '--headless=new',
    `--remote-debugging-port=${CDP_PORT}`,
    `--user-data-dir=${profile}`,
    `--window-size=${VIEWPORT.width},${VIEWPORT.height}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions',
    '--disable-background-networking',
    '--disable-sync',
    '--hide-scrollbars',
    '--force-device-scale-factor=1',
    'about:blank',
  ];
  log('启动独立 profile 的 headless Chrome:', profile);
  const child = spawn(CHROME, args, { stdio: 'ignore', detached: true });
  child.unref();
  const deadline = Date.now() + 20000;
  let lastErr;
  while (Date.now() < deadline) {
    try {
      const v = await httpJson(`http://127.0.0.1:${CDP_PORT}/json/version`);
      log('Chrome 就绪:', v.Browser);
      return { profile, browser: v.Browser };
    } catch (e) {
      lastErr = e;
      await sleep(300);
    }
  }
  throw new Error(`Chrome 未在 20s 内起来: ${lastErr}`);
}

/* ------------------------------------------------------------------ *
 * 3. 页面小工具
 * ------------------------------------------------------------------ */
function makePage(cdp) {
  const pageErrors = [];
  cdp.on('Runtime.exceptionThrown', (p) => {
    pageErrors.push(`exception: ${p.exceptionDetails?.exception?.description || p.exceptionDetails?.text}`);
  });
  cdp.on('Runtime.consoleAPICalled', (p) => {
    if (p.type === 'error') pageErrors.push(`console.error: ${p.args.map((a) => a.value ?? a.description).join(' ')}`);
  });

  const evalJs = async (expression, { awaitPromise = false, timeout } = {}) => {
    const r = await cdp.send('Runtime.evaluate', {
      expression,
      awaitPromise,
      returnByValue: true,
      userGesture: true,
      ...(timeout ? { timeout } : {}),
    });
    if (r.exceptionDetails) {
      throw new Error(`页面脚本异常: ${r.exceptionDetails.exception?.description || r.exceptionDetails.text}`);
    }
    return r.result.value;
  };

  const waitFor = async (label, fn, { timeout = 20000, interval = 200 } = {}) => {
    const deadline = Date.now() + timeout;
    let last;
    while (Date.now() < deadline) {
      try {
        last = await fn();
        if (last) return last;
      } catch (e) {
        last = e.message;
      }
      await sleep(interval);
    }
    throw new Error(`等待「${label}」超时，最后一次结果: ${JSON.stringify(last)}`);
  };

  return { evalJs, waitFor, pageErrors };
}

async function captureTo(cdp, file) {
  const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: false });
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, Buffer.from(data, 'base64'));
  const size = fs.statSync(file).size;
  log(`截图 -> ${path.relative(ROOT, file)} (${(size / 1024).toFixed(0)} KB)`);
  return file;
}

/* ------------------------------------------------------------------ *
 * 4. 主流程
 * ------------------------------------------------------------------ */
async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.mkdirSync(RAW_DIR, { recursive: true });

  let chromeInfo = null;
  try {
    const v = await httpJson(`http://127.0.0.1:${CDP_PORT}/json/version`);
    log('复用已在运行的 Chrome:', v.Browser);
  } catch {
    chromeInfo = await launchChrome();
  }

  const list = await httpJson(`http://127.0.0.1:${CDP_PORT}/json/list`);
  const target = list.find((t) => t.type === 'page');
  if (!target) throw new Error('没有可用的 page target');
  const cdp = await CDP.connect(target.webSocketDebuggerUrl);
  const { evalJs, waitFor, pageErrors } = makePage(cdp);

  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Emulation.setDeviceMetricsOverride', {
    width: VIEWPORT.width,
    height: VIEWPORT.height,
    deviceScaleFactor: VIEWPORT.dpr,
    mobile: false,
    screenWidth: VIEWPORT.width,
    screenHeight: VIEWPORT.height,
  });
  // 关掉 .bar-fill 的条纹动画（App 自己也为 prefers-reduced-motion 关过），截图更稳定
  await cdp.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: 'reduce' }],
  });

  const { identifier } = await cdp.send('Page.addScriptToEvaluateOnNewDocument', {
    source: buildInitScript(),
    runImmediately: true,
  });
  log('已注入 pywebview mock，scriptId =', identifier);

  pageErrors.length = 0;
  await cdp.send('Page.navigate', { url: APP_URL });
  await waitFor('App 挂载完成', () => evalJs(`document.readyState === 'complete' && !!document.querySelector('.app-main')`));
  await waitFor('加载遮罩消失', () => evalJs(`!document.querySelector('.loading-overlay')`), { timeout: 25000 });
  log('页面已就绪');

  const mocked = await evalJs(`!!(window.__PYWEBVIEW_MOCK__ && window.pywebview && window.pywebview.api)`);
  if (!mocked) throw new Error('mock 未生效：window.pywebview.api 不存在');

  // 走真实入口导入记录：等价于用户在下拉框里选中记录（el-select @change -> onRecordChange）
  const importResult = await evalJs(
    `(async () => {
      const host = document.querySelector('.record-selector');
      const inst = host && host.__vueParentComponent;
      if (!inst || !inst.setupState) return { ok: false, reason: '__vueParentComponent 不可用' };
      const uid = ${JSON.stringify(mock.uid)};
      inst.setupState.selectedRecordId = uid;
      await inst.setupState.onRecordChange(uid);
      return { ok: true, uid };
    })()`,
    { awaitPromise: true },
  );
  log('导入记录:', JSON.stringify(importResult));
  if (!importResult?.ok) throw new Error(`导入记录失败: ${JSON.stringify(importResult)}`);

  await waitFor(
    '三池统计渲染',
    () =>
      evalJs(`(() => {
        const spans = [...document.querySelectorAll('.app-main .gacha-summary span')].map((s) => s.textContent.trim());
        return spans.length >= 6 && spans.includes('268') && spans.includes('120') && spans.includes('90') ? spans : false;
      })()`),
    { timeout: 15000 },
  );
  log('三池统计已渲染');

  // 等图标下载完成（图床是 static.gf2gacha-xkl.uk，靠网络）
  const imgState = await waitFor(
    '五星图标加载',
    () =>
      evalJs(`(() => {
        const imgs = [...document.querySelectorAll('.app-main .gacha-item-container img')];
        if (!imgs.length) return false;
        const done = imgs.filter((i) => i.complete).length;
        return done === imgs.length ? { total: imgs.length, done } : false;
      })()`),
    { timeout: 20000 },
  );
  log('图标:', JSON.stringify(imgState));

  // 提示条（五星表来源、导入成功等）会自动消失，等它退干净再拍，避免截图里挂着 toast
  await waitFor('toast 消失', () => evalJs(`document.querySelectorAll('.el-message').length === 0`), {
    timeout: 12000,
  }).catch(() => log('⚠️ toast 没在 12s 内消失，继续截图（会在报告里注明）'));
  await evalJs(`new Promise((r) => (document.fonts ? document.fonts.ready.then(() => r(true)) : r(true)))`, {
    awaitPromise: true,
  });
  await sleep(400);

  const shotOnly = process.env.SHOT_ONLY || '';

  /* ---- 01 主界面三池总览 ---- */
  if (!shotOnly || shotOnly === '01') {
    await captureTo(cdp, path.join(OUT_DIR, '01-overview.png'));
    await captureTo(cdp, path.join(RAW_DIR, '01-overview-full.png'));
  }
  /* ---- 02 角色池详情（同一张原图裁出，2x 像素） ---- */
  const rect = await evalJs(`(() => {
    const col = document.querySelector('.app-main .el-row .el-col:nth-child(1)');
    const item = col && col.querySelector('.app-main-item');
    if (!item) return null;
    const r = item.getBoundingClientRect();
    return { x: r.x, y: r.y, width: r.width, height: r.height };
  })()`);
  if (!rect) throw new Error('找不到角色池列');
  log('角色池列 rect:', JSON.stringify(rect));
  fs.writeFileSync(path.join(RAW_DIR, 'character-rect.json'), JSON.stringify({ rect, dpr: VIEWPORT.dpr, viewport: VIEWPORT }, null, 2));

  /* ---- 03 分享选择弹窗 ---- */
  if (!shotOnly || shotOnly === '03') {
    const clicked = await evalJs(`(() => {
      const btn = [...document.querySelectorAll('.header-right button')].find((b) => b.textContent.includes('分享'));
      if (!btn) return false;
      btn.click();
      return true;
    })()`);
    if (!clicked) throw new Error('找不到「分享」按钮');
    await waitFor(
      '分享弹窗出现',
      () =>
        evalJs(`(() => {
          const dlg = document.querySelector('.el-dialog');
          if (!dlg || !dlg.offsetParent) return false;
          const items = [...dlg.querySelectorAll('.share-pool-list .el-checkbox')];
          return items.length ? items.map((i) => i.textContent.replace(/\\s+/g, ' ').trim()) : false;
        })()`),
      { timeout: 8000 },
    );
    await sleep(900); // 等 dialog / overlay 过渡结束
    await captureTo(cdp, path.join(OUT_DIR, '03-share.png'));
  }

  // 页面错误（Element Plus 报错、mock 抛错都算）
  const hardErrors = pageErrors.filter((e) => !/favicon|DevTools|\[vite\]/i.test(e));
  fs.writeFileSync(path.join(RAW_DIR, 'page-errors.json'), JSON.stringify(pageErrors, null, 2), 'utf8');
  if (hardErrors.length) {
    log('⚠️ 页面错误:');
    for (const e of hardErrors) log('   ', e.slice(0, 300));
  } else {
    log('页面无异常');
  }

  // 顺手把 DOM 里的可见统计抄一份，方便与安卓截图核对
  const summary = await evalJs(`(() => {
    const rows = [...document.querySelectorAll('.app-main .app-main-item')].map((item) => ({
      title: item.querySelector('span')?.textContent.trim(),
      lines: [...item.querySelectorAll('.gacha-summary')].map((e) => e.textContent.replace(/\\s+/g, ' ').trim()),
      ssr: [...item.querySelectorAll('.ssr-item')].map((e) => e.textContent.replace(/\\s+/g, ' ').trim()),
    }));
    return rows;
  })()`);
  fs.writeFileSync(path.join(RAW_DIR, 'dom-summary.json'), JSON.stringify(summary, null, 2), 'utf8');
  log('DOM 统计:', JSON.stringify(summary, null, 1).slice(0, 1800));

  cdp.close();

  if (chromeInfo) {
    try {
      const ver = await httpJson(`http://127.0.0.1:${CDP_PORT}/json/version`);
      const b = await CDP.connect(ver.webSocketDebuggerUrl);
      await b.send('Browser.close');
      b.close();
      log('已关闭临时 Chrome，profile:', chromeInfo.profile);
    } catch (e) {
      log('关闭 Chrome 失败（可手工清理）:', e.message);
    }
  }
}

main().catch((e) => {
  console.error('[shot] 失败:', e.message);
  process.exitCode = 1;
});
