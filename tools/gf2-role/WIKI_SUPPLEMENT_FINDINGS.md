# 本地详情与官方 Wiki 对照补全

日期：2026-10-18。

此文件是前一轮 Wiki 合并的历史记录。用户澄清目标后，已根据 Wiki 线索在本地找到 ShareLimit 引用链，当前应使用 [纯本地解析结果](LOCAL_REFERENCE_RESOLUTION_FINDINGS.md)，无需依赖本文件中的 Wiki 覆盖映射。

## 已完成

按角色相同 ID 检查官方 Wiki 的 16 个详情页，校验接口返回 ID 和名称。解析正文与 HTML `data-dec` 悬浮说明，得到 17 组缺失引用的名称及完整说明。补齐此前 72 条技能等级记录、4 条 Buff 记录中的正文占位符；另补齐 1 条只在升级说明中缺名称的记录。共补充 77 条记录，正文和升级说明的未解析占位符均为 0。

- [合并详情 JSON](../../logs/catalog_probe_20261018/catalog_details_with_wiki.json)
- [补全报告与剩余项](../../logs/catalog_probe_20261018/wiki_supplement_report.json)
- [原始纯本地导出](../../logs/catalog_probe_20261018/local_catalog_details.json)
- [补全程序](supplement_wiki_catalog.py)
- [已审核的引用映射](wiki_reference_overrides.json)

仅补名称和关联 Wiki 悬浮说明，不用 Wiki 整段描述替换本地技能正文或数值。原始本地文本保存为 `localDescription` / `localUpgradeDescription`，原引用保存在 `localReferences`；`wikiReferences` 保存完整效果说明及所在栏目，`wikiSources` 保存页面 URL、ID、名称和缓存 SHA-256。基础属性配置和未完成的成长计算不受这次文字补全影响。

复现命令（已有缓存直接读取，不重复请求）：

```powershell
python tools/gf2-role/supplement_wiki_catalog.py --local logs/catalog_probe_20261018/local_catalog_details.json --cache logs/catalog_probe_20261018
```

没有缓存的角色才查询 `POST https://gf2-bbs-api.exiliumgf.com/wiki/hero_detail`，请求为 `{"id": 角色ID}`。不访问账号接口，不上传资源。接口失败记录为失败项，不无限重试。

## 补齐的效果名称

| 角色与官方页面 | 本地引用 | 补齐名称 |
|---|---|---|
| [黛烟 1032](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1032) | `0:-1,103209,1` | 校音 |
| [莫辛纳甘 1033](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1033) | `0:-1,103307,1` | 积极作战 |
| [乌尔丽德 1037](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1037) | `0:-1,10370401,2` | 迷彩 |
| [维克托 1044](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1044) | `0:-1,104400,1` | 过热自燃 |
| [春田 1047](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1047) | `0:-1,10470701,1` | 满溢关怀 |
| 同上 | `0:-1,104700,1` | 塔瑞兹；鹰眼洞察 Lv.2/3 对应塔瑞兹·强协 |
| [米什缇 1051](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1051) | `0:-1,10510700,1` | 激斗模式 |
| 同上 | `0:-1,10510800,1` | 补丁模式 |
| 同上 | `0:-1,10510701,1` | 梦境亢奋 |
| [可露凯 1052](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1052) | `0:-1,10520800,1` | 好胜心 |
| 同上 | `0:340602,1` | 强酸倾压；也确认同名本地显示行 340602 已存在，属于导出器暂未处理的引用格式 |
| [妮基塔 1055](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1055) | `0:-1,10550501,1` | 畏罪 |
| [樱花 1068](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1068) | `0:-1,10680400,1` | 吉运 |
| [夏安 1070](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1070) | `0:-1,107007,1` | 靶心 |
| [贝丝蒂 1071](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1071) | `0:-1,107107,1` | “小可爱” |
| [米蒂尔 1077](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1077) | `0:-1,10770800,1` | 拟合共鸣 |
| [芙铃 1078](https://gf2-bbs.exiliumgf.com/wiki/doll?id=1078) | `0:-1,10780401,1` | 巡狩本能 |

例如黛烟“清商和鸣”已经补成“获得3层校音；获得定弦，持续1回合。并获得1次指令追加。”校音的 Wiki 悬浮说明也已保存在 `wikiReferences` 中，可用于详情弹窗。

## 版本差异与处理

- 同名效果的基础/升级说明可能不同，保存所有原文和栏目，不把效果数值混为一个通用版本。
- 春田“塔瑞兹”与“塔瑞兹·强协”分别保存说明，只有 Wiki 明确对应的鹰眼洞察升级记录使用强协名称。
- 米蒂尔某处升级正文把应引用“拟合共鸣”的位置写成“银幕头衔”；Wiki 基础技能、多处升级说明及本地 `BattleSkillDisplayData[10770800]` 一致为“拟合共鸣”，因此采用这些一致证据，记录冲突。
- 芙铃基础技能一处写“巡兽本能”，但 Wiki 悬浮说明、升级正文与本地 `BattleDictionaryData[107804010]` 均为“巡狩本能”，因此采用后者并保留差异说明。
- 夏安固键正文中的“靶心”没有悬浮标签，但该角色其他技能含同名悬浮说明，已经交叉验证。

## 仍未找到的独立说明

### 针的内部技能 10852002

本地 `BattleSkillData[10852002]` 存在，但 `BattleSkillDisplayData[10852002]` 不存在；运行配置 f17 为 `5,2,10852003,1,0,0`。针的 Wiki 刊载“入殓奏鸣曲”整体说明，没有为该内部 ID 提供可独立对应的条目。因此保留为 `no-independent-description-found`，不把主技能说明冒充这个 ID 的说明。

### 索普的闲置引用 0:107608012

仅出现在本地“恶性撕咬 Lv.2”引用列表，实际正文和升级说明均未使用该索引。Wiki 没有能可靠指向该内部 ID 的独立效果说明，因此保留未解析引用。它不会在当前描述中留下占位符。

### 先前 4 个缺少显示记录的 ID 中，有 3 个已确认是占位项

| 内部技能 ID | 本地运行表 f10 | 对应显示表说明 |
|---|---:|---|
| 乌尔丽德 `10372002` | 10000 | 空技能-用于各种占位和临时功能使用 |
| 六分仪 `10732002` | 10000 | 空技能-用于各种占位和临时功能使用 |
| 针 `10852004` | 10000 | 空技能-用于各种占位和临时功能使用 |

这三项已从待补用户说明中排除，仍保存原始运行表证据。乌尔丽德“追猎者”、六分仪“镇魂歌”和针“入殓奏鸣曲”的主体说明已有记录，不能把内部占位项解释成主体说明缺失。

## 验证范围

覆盖全部原有未解析正文与升级说明；合并前后的角色、武器、基础属性及已经解析的正文保持一致。新增名称与悬浮定义均追溯到对应角色 ID 的官方页面，保留来源摘要与审核映射。原始纯本地文件保持独立，后续可重新导出并重复补全。
