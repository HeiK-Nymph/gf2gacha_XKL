const R2_BASE = 'https://r2.gf2gacha-xkl.uk'

export const REPO_URL = 'https://github.com/HeiK-Nymph/gf2gacha_XKL'
export const RELEASES_URL = `${REPO_URL}/releases`
export const GUIDE_URL = 'https://www.bilibili.com/video/BV1oaz2BsEPo/'

/**
 * 两个平台的发布信息。
 * version / size / sha256 是 R2 读不到时的兜底值，
 * 页面加载后会尝试用远端 version.json 覆盖。
 */
export const platforms = [
  {
    id: 'pc',
    label: '电脑版',
    system: 'Windows 10 / 11',
    icon: 'monitor',
    accent: 'gold',
    fileName: 'gf2gacha_XKL.zip',
    downloadUrl: `${R2_BASE}/gf2gacha_XKL.zip`,
    versionUrl: `${R2_BASE}/version.json`,
    version: '1.1.10',
    size: 37738036,
    sha256: 'c8f8fc06cbb20fd5894f1338b1aa776b61b0af3399c7a7be9695875a6f7b6af7',
    summary: '内置代理抓一次游戏请求，之后反复重放。五个池子一起统计。',
    requirements: ['系统：Windows 10 / 11', '首次需装一次 mitmproxy 证书', '进一次「招募 · 访问详情」完成捕获'],
    steps: [
      '解压后运行主程序，点「安装证书」并按指引安装到受信任的根证书颁发机构。',
      '打开游戏，进入「招募 → 访问详情」，等状态栏变成「已捕获」。',
      '回到工具点「更新记录」，五个池子的数据会一起拉取。',
    ],
  },
  {
    id: 'android',
    label: '手机版',
    system: 'Android',
    icon: 'smartphone',
    accent: 'green',
    fileName: 'gf2gacha_XKL_android.apk',
    downloadUrl: `${R2_BASE}/gf2gacha_XKL_android.apk`,
    versionUrl: `${R2_BASE}/version_android.json`,
    version: '0.1.9',
    size: 9411378,
    sha256: '30ba6f6374d65d8ac95c248018fb154e24bddf19c9d7a261c0357156fbcc29e5',
    summary: '只要一部安卓手机：不用电脑、不用 root、不用证书、不用 VPN。',
    requirements: ['系统：Android 7.0+，64位ARM设备', '官服 / B服 · 短信或账号密码登录', '无需 root / 证书 / VPN'],
    steps: [
      '安装 APK，首次会提示「未知来源」，允许即可。',
      '打开 App →「添加账号」→ 选择官服或B服 → 短信或账号密码登录。',
      '之后直接进抽卡页，「分享」可导出竖版长图。',
    ],
  },
]

export function formatSize(bytes) {
  if (!bytes && bytes !== 0) return '--'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function shortHash(hash) {
  if (!hash) return '--'
  return `${hash.slice(0, 12)}…${hash.slice(-6)}`
}
