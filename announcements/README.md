# 手机端公告资源

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
  "body": "公告正文，用 \\n 换行",
  "images": ["images/example.png"],
  "published_at": 1792680563,
  "expires_at": 0
}
```

- `published_at` / `expires_at` 使用 Unix 秒；`expires_at=0` 表示长期有效。
- 图片路径相对 `announcements/`，支持 PNG / JPG / WebP，单条公告最多加载 6 张。
- App 每次回到前台会检查，5 分钟内不重复请求；最新公告未读时自动弹出。
- 更新顺序：先上传图片，最后上传 `manifest.json`，避免用户读到新清单但图片还是 404。
- 清单建议 `Cache-Control: no-cache, max-age=60`；图片可长缓存并使用新文件名。

## 上传

```powershell
$env:GF2_GACHA_MANAGER_DIR = 'D:\myproject\McpAndSkill\mcp\gf2-gacha-manager'
python tools/upload_announcements.py          # 预览
python tools/upload_announcements.py --publish # 实际上传
```

脚本要求当前环境已有 `R2_ACCESS_KEY_ID`、`R2_SECRET_ACCESS_KEY`、`R2_ENDPOINT`、`R2_BUCKET`。
