# 本地角色与武器详情调查

2026-10-18。本次数据全部来自已安装游戏的磁盘文件，没有调用 Wiki、网络接口或游戏进程。只新增研究工具和导出文件，未修改业务数据文件。

后续根据 Wiki 名称线索找到了遗漏的本地 ShareLimit 引用链，并修正纯本地解析器，见 [当前本地解析结果](LOCAL_REFERENCE_RESOLUTION_FINDINGS.md)。本文保留最初纯本地阶段的观测，以下72条缺口和4条警告是旧快照，当前结果已更新。

## 结果与复现

现有 `json/ssr.json` 的 54 名五星角色、65 把五星武器全部通过 ID、名称校验。导出包含 1,536 条关联技能显示记录、489 条 Buff 显示记录、132 条战斗术语；这些包含各技能等级及附属效果，不能理解为 1,536 个独立角色技能。

- [完整本地导出 JSON](../../logs/catalog_probe_20261018/local_catalog_details.json)
- [离线导出程序](export_local_catalog.py)
- [单表行与关联调查工具](local_catalog_probe.py)
- [当前程序集属性字段证据](LOCAL_SCHEMA_FINDINGS.md)

复现：

```powershell
python tools/gf2-role/export_local_catalog.py --output logs/catalog_probe_20261018/local_catalog_details.json
```

可用 `--tables <Table目录>` 显式指定本地目录。默认沿现有 `backend/ssr_parser.py` 从 Player.log 定位。JSON 的 `sources` 记录每个实际读取表的绝对路径和 SHA-256；`warnings` 和未解析占位符明确保留。

## 已验证的本地表关系

下列是当前表数据的直接关联观测；除 PropertyData 之外，不声称已恢复混淆字段的官方命名。

| 来源 | 对应内容 |
|---|---|
| `GunData.f2/f6/f7/f67` + 中文语言表 | 角色名称、简介、语录、武器语录 |
| `GunData.f11 -> GunCharacterData`，档案 `f9` 回链角色 ID | 档案；针为 `1085 -> 70 -> 1085` |
| `GunCharacterData.f12/f13/f16/f18/f19` | 中文声优、日文声优、型号、武器名、所属组织 |
| `GunData.f13 -> GunDutyData.f2` | 职业/定位 |
| `GunData.f23 -> GunWeaponTypeData.f2` | 武器类别 |
| `GunData.f18 -> BattleSkillDisplayData` | 普攻描述 |
| `GunGradeData.f2` 角色 ID，`f4/f14` 技能 ID 列表 | 各椎体阶层关联技能、特殊技能；同时支持 unpacked 与 packed repeated 字段 |
| `TalentKeyData.f9/f15` 角色 ID，`f6` 技能显示 ID，`f5` 属性 ID | 固键、共键、契合键及属性配置 |
| `GunData.f40 -> PropertyData` | 角色基础属性配置 |
| `GunData.f29 -> GunClassData.f2`，`f8 -> PropertyData` | 等级上限/突破阶段的配置属性；阶段记录保留原值，不计算最终属性 |
| `GunLevelExpData.f4 -> PropertyData` | 等级成长配置；导出 60 行原始记录 |
| `GunWeaponData.f2/f3/f8/f9` | 武器名称、简介、图标资源名、模型资源路径 |
| `GunWeaponData.f4 -> GunWeaponTypeData.f2` | 武器类别 |
| `GunWeaponData.f21 -> PropertyData` | 武器基础属性配置 |
| `WeaponBreakData.f2` 武器 ID，`f3` 等级，`f4` 技能显示 ID | 武器 Lv.1～6 技能；不把零级占位行当作有效技能等级 |
| `BattleWeaponData.f4/f5 -> BattleSkillDisplayData` | 武器特质、烙印技能 |
| `BattleSkillDisplayData.f2/f3/f8/f9/f22` | 名称、描述模板、升级说明、等级、技能类型 |
| `BattleSkillDisplayData.f4` 和 Buff/术语表同形字段 | 描述中的关联名称；保留原始引用字符串与解析路径 |

## 针（1085）的直接例子

- 定位：支援；武器类别：刀。
- 型号：STR-03A482；组织：艾莫号·三代人形小队。
- 中文声优：姜贺；日文声优：川澄绫子。
- `GunData[1085].f40=11085 -> PropertyData[11085]`：攻击 87、生命 246、防御 67、稳态指数 10；行动力、暴击、暴伤原始值分别为 900、200、1200。**这是基础配置，未计算等级和培养加成。**
- `BattleSkillDisplayData[10850701]` 和弦协奏：获得 1 层细胞共鸣，持续 2 回合；技能后可使用大三和弦、小三和弦、减三和弦。原描述中的 `{0}..{3}` 已通过本地 Buff 与战斗术语表补全名称。
- `TalentKeyData[208501] -> BattleSkillDisplayData[10850901]` 固键·晨间问候：战斗开始时获得 1 点导染指数，自身和距离自身最近的使用刀的友方人形获得 2 点通透指数。
- `TalentKeyData[901085] -> BattleSkillDisplayData[10850907]` 共键·竭诚为您服务：若消耗导染指数，则本回合造成的伤害提高 10%。其属性配置另指向 `PropertyData[8001048]` 的 `crit=50`。
- 契合键·杰奎琳之泪：`PropertyData[8200068]` 的 `critMult/powPercent/maxHpPercent` 原始值均为 30。

## 天鹅之死（10853）的直接例子

- `GunWeaponData[10853].f21=41223 -> PropertyData[41223]`：基础攻击配置 50，暴击伤害原始值 250。**不是声称 60 级攻击为 50；单位与成长计算尚未完成。**
- `WeaponBreakData[108531..108536].f4 -> BattleSkillDisplayData[5108531..5108536]`：执事热忱 Lv.1～6 的物理伤害提升分别为 20%、25%、30%、35%、40%、45%；友方单位主动斩域技能伤害提高 10%；回合外物理伤害后获得 1 点通透指数，每回合至多 6 点。
- `BattleWeaponData[10853].f4=5108539`：无视目标 10% 防御力，造成近战伤害时额外无视其 10% 防御力。
- `BattleWeaponData[10853].f5=5108530`：对持有防御类减益的目标造成伤害提高 2.5%，对生骸造成的伤害提高 2.5%。

## 文字占位符与覆盖边界

发现战斗术语表 `BattleDictionaryData`，其中 `90118` 是“护盾”、`900240` 是“实体召唤物”。不能把同一数字的语言表条目当作对应术语，也不能把所有 `1:ID` 引用都查到技能表。

- `1:ID` 按 `BattleDictionaryData` 查名称；术语有同 ID 技能显示记录时也保留关联技能。
- `0:ID`、`0:-1,ID,等级` 按 Buff 名称关联；直接显示行不存在时，记录经 `BuffClassData.f2` 或 `BattleBuffData.f3` 的解析路径。这是数据关系推导，不是执行客户端格式化器的结果。
- 导出保留富文本原模板、解析后的描述、所有引用和 `unresolvedDescriptionPlaceholders`。
- 当前 1,536 条技能显示记录中仍有 **72 条描述含未补全占位符**；不能称所有说明完整解析。
- `10372002`、`10732002`、`10852002`、`10852004` 被椎体特殊技能列表引用，但没有对应 `BattleSkillDisplayData` 显示行；明确列为 warning，不删除引用或补写文本。
- 本地针普攻 `10850101` 写的是“周围半径 1 格、80% 攻击力的近战物理伤害”；此前 Wiki 写成了半径 8 格。导出以本地原文为准，不用 Wiki 覆盖。
- 成长倍率、百分比/行动力单位、突破叠加顺序、取整规则与玩家最终面板仍需客户端计算依据。程序只提供基础及成长配置，未硬编码 Wiki 数值。

## 验证

离线运行覆盖全部现有 SSR ID；角色、武器名称不一致时程序中止。54 名角色均有回链一致的档案与天赋记录，65 把武器均有有效技能等级。样例直接复读原表并核对属性元数据、六级技能、固键及 Buff/术语名称关联。输出记录源表摘要以便后续版本对比。
