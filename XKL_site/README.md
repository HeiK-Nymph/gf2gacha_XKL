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
构建产物是扁平的（`assetsDir: ''`），`index.html` 旁边直接放 js/css，方便整包拖到任意托管。

## 线上部署

项目站点：**https://heik-nymph.github.io/gf2gacha_XKL/**

`.github/workflows/pages.yml` 会在 `XKL_site/**` 有推送时自动构建并发布到 GitHub Pages
（`workflow_dispatch` 也能手动触发）。本地不用构建、也不用提交产物，push 到 `main` 等两分钟即可。

发版流程：

```powershell
git add XKL_site && git commit -m "feat(site): 改了什么" && git push
```

Pages 的 `Source` 已经设成 **GitHub Actions**；首次启用必须去仓库 Settings → Pages 手动选一次，
工作流里的 `configure-pages ... enablement: true` 在权限不足时无法代替这一步。

## 下载信息从哪来

`src/data/releases.js` 里保存了两个平台的 R2 地址、文件名、体积和 sha256，页面加载后会再尝试
读取 R2 上的 `version.json` / `version_android.json` 覆盖它们：

| 平台 | 版本文件 | 安装包 |
|---|---|---|
| 电脑版 | `https://r2.gf2gacha-xkl.uk/version.json` | `https://r2.gf2gacha-xkl.uk/gf2gacha_XKL.zip` |
| 手机版 | `https://r2.gf2gacha-xkl.uk/version_android.json` | `https://r2.gf2gacha-xkl.uk/gf2gacha_XKL_android.apk` |

R2 桶 `gf2gachaxkl` 已配好 CORS 策略，所以页面加载时会直接读到最新的版本号（页脚会显示
「版本信息已从 R2 读取」）。当前规则：

```json
[{
  "AllowedOrigins": ["*"],
  "AllowedMethods": ["GET", "HEAD"],
  "AllowedHeaders": ["*"],
  "ExposeHeaders": ["ETag", "Content-Length"],
  "MaxAgeSeconds": 3600
}]
```

读到的只是版本 / 体积 / sha256 三个值；万一哪天读不到（桶被改、网络抖动），页面会自动退回
`releases.js` 里的内置值，不会开天窗。下载按钮始终是普通 `<a download>`，本来就不依赖 CORS。

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
