# 桌面端 / 手机端公告资源

R2 桶根目录下的专用公告文件夹是：

```text
announcements/
├── manifest.json
└── images/
    └── announcement-launch.png
```

公开地址：

- 清单：`https://r2.gf2gacha-xkl.uk/announcements/manifest.json`
- 图片：`https://r2.gf2gacha-xkl.uk/announcements/images/<文件名>`

## 发布一条公告

编辑 `manifest.json` 的 `announcements` 数组。App 会展示 `active=true` 中
`published_at` 最新的一条；公告 ID 变化后，用户会再次看到未读提示。

```json
{
  "id": "唯一-id，发布后不要复用",
  "active": true,
  "title": "公告标题",
  "body": "公告正文，用 \\n 换行；仅图片公告可留空",
  "images": ["images/example.png"],
  "published_at": 1792680563,
  "expires_at": 0
}
```

- `published_at` / `expires_at` 使用 Unix 秒；`expires_at=0` 表示长期有效。
- `title` 必填；正文与图片至少有一项。仅图片公告可将 `body` 设为空字符串。
- 图片路径相对 `announcements/`，支持 PNG / JPG / WebP，单条公告最多加载 6 张。
- 两端都只在应用打开时自动检查一次；最新公告未读时自动弹出，不在打开期间定时轮询。
- 公告清单会持久化到本机，10 分钟内重新打开直接使用缓存，不请求 R2；超过 10 分钟才检查更新。
- 手动点击「公告」始终绕过缓存强制刷新；网络失败时回退到最近一次成功缓存。
- 桌面端标题栏的「公告」按钮可随时强制刷新并重新查看，图片支持点击放大预览。
- 更新顺序：先上传图片，最后上传 `manifest.json`，避免用户读到新清单但图片还是 404。
- 清单建议 `Cache-Control: no-cache, max-age=60`；图片可长缓存并使用新文件名。

## 本地预览（不访问 R2）

修改清单或图片后，先生成本地预览。可以直接双击 `tools\preview_announcements.bat`，或运行：

```powershell
python tools\announcement_preview.py
```

脚本会读取 `announcements/manifest.json`，把本地图片直接内嵌到一个独立 HTML 中，并自动打开浏览器。公告内容超长时，桌面端和手机端预览都能上下滚动，滚动条会隐藏。
页面会并排展示桌面端与安卓端的公告弹窗，可切换：

- 打开 App · 新公告（未读）
- 手动打开 · 已读
- 缓存回退 · 网络失败
- 仅看入口按钮
- 暂无公告

下方还会列出清单中每条公告的状态（启用中 / 停用 / 已过期 / 字段错误），
并提示缺图、重复 ID、超过 6 张图片等问题。

预览文件生成在：

```text
test/announcement-preview/index.html
```

这个工具**只读本地文件，不访问 R2，也不会上传**。确认排布无误后，再执行下面的上传步骤。

## 上传

```powershell
$env:GF2_GACHA_MANAGER_DIR = 'D:\myproject\McpAndSkill\mcp\gf2-gacha-manager'
python tools/upload_announcements.py          # 预览
python tools/upload_announcements.py --publish # 实际上传
```

脚本要求当前环境已有 `R2_ACCESS_KEY_ID`、`R2_SECRET_ACCESS_KEY`、`R2_ENDPOINT`、`R2_BUCKET`。
