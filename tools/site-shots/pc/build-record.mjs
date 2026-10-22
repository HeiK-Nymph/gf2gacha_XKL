#!/usr/bin/env node
/**
 * 把 tools/site-shots/fake-accounts.json（安卓截图用的假账号）转成
 * PC 版前端真正吃的记录结构，供截图 harness 注入。
 *
 * PC 结构来源（只反推形状，不读真实记录内容）：
 *   main.py:512 get_record_list  -> {status, data:[recordId...]}
 *   main.py:547 import_record    -> {status, data: <记录文件全文>}
 *   main.py:572 export_record    -> 记录文件 = {permanent_pool, character_pool,
 *                                  weapon_pool, custom_character_pool, custom_weapon_pool}
 *   每个 pool 是「页」数组；一页 = {code, message, data:{list, next}}
 *   一条抽卡 = {pool_id, item, time, item_num}
 *   frontend/src/components/GachaItem.vue:131 用 page.data.list flatMap
 *
 * 输出：tools/site-shots/pc/mock-data.json（中间产物，不进仓库发布物）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..', '..');

const fake = JSON.parse(fs.readFileSync(path.join(ROOT, 'tools', 'site-shots', 'fake-accounts.json'), 'utf8'));
const ssr = JSON.parse(fs.readFileSync(path.join(ROOT, 'json', 'ssr.json'), 'utf8'));
const version = JSON.parse(fs.readFileSync(path.join(ROOT, 'version.json'), 'utf8'));

// 安卓 AccountStore 的 pool key -> PC 记录文件的 pool key
const POOL_KEY = {
  '1': 'permanent_pool',
  '3': 'character_pool',
  '4': 'weapon_pool',
  '6': 'custom_character_pool',
  '7': 'custom_weapon_pool',
};

const account = fake.accounts.find((a) => a.uid === fake.current) || fake.accounts[0];
/** 每个假账号各自一份 PC 记录，切换下拉框时数据也对得上（截图只用 account） */
const recordsByUid = {};

/** 一个池子的记录 -> 「页」数组（真实分页每页 6 条、最新页在前；这里保留同样的外层形状） */
function toPages(rows, pageSize = 20) {
  const list = [...rows].sort((a, b) => b.time - a.time); // 接口就是新在前
  const pages = [];
  for (let i = 0; i < list.length; i += pageSize) {
    const chunk = list.slice(i, i + pageSize);
    const isLast = i + pageSize >= list.length;
    pages.push({
      code: 0,
      message: 'ok',
      data: {
        list: chunk.map((row) => ({
          pool_id: row.pool_id,
          item: row.item,
          time: row.time,
          item_num: row.item_num ?? 1,
        })),
        next: isLast ? '' : String(i + pageSize),
      },
    });
  }
  if (pages.length === 0) pages.push({ code: 0, message: 'ok', data: { list: [], next: '' } });
  return pages;
}

function buildRecord(acct) {
  const empty = {
    permanent_pool: [],
    character_pool: [],
    weapon_pool: [],
    custom_character_pool: [],
    custom_weapon_pool: [],
  };
  const out = { ...empty };
  for (const [key, rows] of Object.entries(acct.records || {})) {
    const pool = POOL_KEY[key];
    if (!pool) throw new Error(`未知 pool key: ${key}`);
    out[pool] = toPages(rows);
  }
  return out;
}

for (const acct of fake.accounts) recordsByUid[acct.uid] = buildRecord(acct);
const record = recordsByUid[account.uid];

/* ------------------------------------------------------------------ *
 * 用 GachaItem.vue 的算法复算一遍统计，确保与安卓截图口径一致：
 *   totalDrawCount = 全部抽数
 *   ssrTotal       = 五星数
 *   waiCount       = 五星中属于常驻池的数量（角色/武器池）
 *   currentPadCount= 最新五星的绝对索引（= 之后还没出金的抽数）
 * ------------------------------------------------------------------ */
const PERM = new Set(Object.keys(ssr.SSR_permanent || {}));
const MAPS = {
  character_pool: { ...ssr.SSR_permanent, ...ssr.SSR_character },
  weapon_pool: { ...ssr.SSR_permanent, ...ssr.SSR_weapon },
  permanent_pool: { ...ssr.SSR_permanent },
  custom_character_pool: { ...ssr.SSR_permanent, ...ssr.SSR_character },
  custom_weapon_pool: { ...ssr.SSR_permanent, ...ssr.SSR_weapon },
};

function stats(poolKey) {
  const draws = record[poolKey]
    .flatMap((page, pageIndex) => (page.data?.list || []).map((d) => ({ ...d, pageIndex })))
    .sort((a, b) => (b.time !== a.time ? b.time - a.time : a.pageIndex - b.pageIndex))
    .map((d, absoluteIndex) => ({ ...d, absoluteIndex }));
  const map = MAPS[poolKey];
  const ssrList = draws
    .filter((d) => Object.prototype.hasOwnProperty.call(map, d.item))
    .map((d) => ({
      name: map[d.item],
      item: d.item,
      drawIndex: d.absoluteIndex,
      isWai: PERM.has(String(d.item)),
    }));
  const total = draws.length;
  const list = ssrList.map((cur, i) => {
    let cost;
    if (ssrList.length === 1) cost = total - cur.drawIndex;
    else if (i < ssrList.length - 1) cost = ssrList[i + 1].drawIndex - cur.drawIndex;
    else cost = total - cur.drawIndex;
    return { ...cur, costDraws: cost };
  });
  const wai = poolKey === 'permanent_pool' ? 0 : list.filter((x) => x.isWai).length;
  const pad = list.length > 0 ? list[0].drawIndex : total;
  return { total, ssrTotal: list.length, wai, pad, rows: list };
}

const report = {};
for (const poolKey of Object.keys(record)) {
  const s = stats(poolKey);
  report[poolKey] = {
    total: s.total,
    ssrTotal: s.ssrTotal,
    wai: s.wai,
    pad: s.pad,
    ssr: s.rows.map((r) => `${r.name}(${r.costDraws}${r.isWai ? ',歪' : ''})`),
  };
}

const status = {
  status: 'success',
  proxy: { ready: true, system_proxy: true, port: 11111, error: '' },
  capture: {
    exists: true,
    size: 4096,
    has_authorization: true,
    replayable: true,
    captured_at: '2026-10-22 19:31:05',
    age_text: '刚捕获',
    stale: false,
  },
  log_path: 'D:\\myproject\\gf2gacha_XKL\\logs\\gf2gacha_XKL.log',
};

const mock = {
  _note: '截图用假数据，无真实 UID / 手机号 / 令牌',
  uid: account.uid,
  phone: account.phone,
  recordList: fake.accounts.map((a) => a.uid),
  records: recordsByUid,
  ssr,
  version: version.current_version,
  status,
};

const out = path.join(HERE, 'mock-data.json');
fs.writeFileSync(out, JSON.stringify(mock, null, 2), 'utf8');

console.log(`written ${path.relative(ROOT, out)} (${(fs.statSync(out).size / 1024).toFixed(1)} KB)`);
console.log('uid:', mock.uid, 'recordList:', mock.recordList.join(','));
for (const [pool, r] of Object.entries(report)) {
  console.log(
    `${pool.padEnd(22)} 共 ${String(r.total).padStart(3)} 抽 · 五星 ${r.ssrTotal} · 歪 ${r.wai} · 垫 ${r.pad}` +
      (r.ssr.length ? `  <- ${r.ssr.join(' / ')}` : ''),
  );
}
