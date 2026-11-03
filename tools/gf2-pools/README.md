# gf2-pools：从本地游戏表生成 `json/pools.json`

`json/pools.json` 是卡池映射，上传到 R2 桶根目录后供微信小程序端消费
（`XKL_WeChat/cloudfunctions/simulator/dataset.js` 只取 `type_id ∈ {3,4}` 的
人形/武器 UP 池，用 `name` 作为卡池显示名、`start_time_text` 的日期作为上榜日期）。

## 生成

```powershell
python tools\gf2-pools\generate_pools_mapping.py
# 指定表目录 / 与旧文件逐条校验
python tools\gf2-pools\generate_pools_mapping.py --tables "<游戏>\LocalCache\Data\Table" --verify-against json\pools.json
```

表目录默认按 `--tables` → `GF2_TABLE_DIR` → `Player.log` 顺序自动定位；仓库根默认按
`--root` → `GF2GACHA_ROOT` → 当前目录顺序定位（都要求含 `json/ssr.json`）。

MCP `sync_local_tables(groups=["pools"])` 会以仓库根为 cwd 调用本脚本，输出
`json/pools.json`；脚本在 `cache/generate_pools_mapping.py` 与
`tools/gf2-pools/generate_pools_mapping.py` 两处都会被识别（`cache/` 被 .gitignore
忽略，所以本体放在 `tools/`）。

## 字段口径（由旧文件 276 条逐条反推，276/276 完全一致）

| 字段 | 来源 |
|---|---|
| `type_id` / `type_name` | `GachaData.type` / `GachaTypeListData.name` |
| `name` | `type` 3/4 取 **UP 五星名**；其余取卡池表名 |
| `start_time` / `end_time` | 表内秒级时间戳 |
| `start_time_text` / `end_time_text` | 时间戳按 **UTC+8** 格式化 `YYYY-MM-DD HH:MM:SS`；为 0 时 `null` |
| `up_5` / `up_4` | `type 3 → gunUpItem`、`type 4 → weaponUpItem` 里的 `5:…` / `4:…` 分组（冒号分隔多 id） |
| `up_5[].kind` / `up_4[].kind` | `ItemData.type == 20` → `weapon`，否则 `character` |

- `type` 6 / 7（自选UP）历史文件从未收录，默认跳过；`--include-self-select` 可纳入。
- 旧文件里有、本次表里已没有的卡池默认**原样保留**（避免历史记录/小程序引用断链），
  并在 summary 的 `kept_from_previous` 里列出。
- 键按卡池 id 数值升序排列，2 空格缩进，`ensure_ascii=False`，UTF-8 + LF。

## 校验记录（2026-11-03）

```
旧 276 条 → 新 284 条：changed 0、missing 0、added 8
新增：296001 破坏者 / 297001 盖娅终结 / 298001 希丽雅 / 299001 斯诺特拉 /
      300001 索普 / 301001 碎穹嚎歌 / 302001 索米 / 303001 未言使命（均 2026-11-03 09:00 开池）
二次运行：284 条全部 unchanged（幂等）
小程序 dataset.build()：274 个 UP 池，最新 8 条日期均为 2026-11-03，up5/up4 正确映射
```
