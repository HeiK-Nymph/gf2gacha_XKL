# 夏克里助手 · 官网

给「夏克里助手」（《少女前线2：追放》抽卡记录工具）做的落地页，电脑版（Windows）和手机版（Android）的安装包
都直接走 R2 直链下载。

布局参考 [kazumi.app](https://kazumi.app/)：顶部胶囊导航 → 主视觉 + 平台条 → 下载卡片 → 功能 →
教程 → 结尾引导 → 页脚；窄屏时导航自动变成底部标签栏。

## 技术栈

- Vue 3（`<script setup>`）+ Vite，无 UI 框架，样式全部是原生 CSS + 设计变量
- [@lucide/vue](https://lucide.dev/) 提供图标（lucide 已不再收录品牌图标，GitHub 标志是内联 SVG）
- 暗金配色取自客户端 `XKL_android/app/src/main/res/values/colors.xml`，另有一套浅色主题

## 本地开发

```powershell
cd XKL_site
npm install
npm run dev      # http://localhost:5173
npm run build    # 产物在 dist/，纯静态，可直接丢到任意托管 / CDN
```

`base` 是 `./`，所有资源用相对路径，放到子目录（例如 `https://example.com/gf2/`）也能正常显示。

## 下载信息从哪来

`src/data/releases.js` 里保存了两个平台的 R2 地址、文件名、体积和 sha256，页面加载后会再尝试
读取 R2 上的 `version.json` / `version_android.json` 覆盖它们：

| 平台 | 版本文件 | 安装包 |
|---|---|---|
| 电脑版 | `https://r2.gf2gacha-xkl.uk/version.json` | `https://r2.gf2gacha-xkl.uk/gf2gacha_XKL.zip` |
| 手机版 | `https://r2.gf2gacha-xkl.uk/version_android.json` | `https://r2.gf2gacha-xkl.uk/gf2gacha_XKL_android.apk` |

目前 R2 没配 CORS，浏览器跨域读这两个 json 会被拦掉，页面会自动用内置的兜底值（浏览器控制台会
看到两条 CORS 报错，属预期）。想让它自动跟随最新版本，给 R2 桶加一条 CORS 规则允许 `GET` 即可：

```json
[{ "AllowedOrigins": ["*"], "AllowedMethods": ["GET"], "AllowedHeaders": ["*"] }]
```

下载按钮是普通 `<a download>`，不需要 CORS，两种情况下都能正常下载。

## 目录

```
src/
  App.vue                    页面骨架 + 主题切换 + 平台高亮
  data/releases.js           平台信息 / R2 地址 / 兜底版本数据
  composables/useReleases.js 读取 R2 版本信息（失败即兜底）
  components/                Header / Hero / 平台条 / 下载卡片 / 功能 / 教程 / 结尾 / 页脚
  style.css                  设计变量与通用积木
public/                      favicon.png、mascot.png（主视觉用的应用图标）
```

## 改版小提示

- 换主视觉：替换 `public/mascot.png`（正方形效果最好）
- 换配色：改 `src/style.css` 里 `:root` 和 `[data-theme="light"]` 的变量即可
- 改文案 / 步骤：`src/data/releases.js` 里每个平台的 `summary`、`requirements`、`steps`、`notes`
