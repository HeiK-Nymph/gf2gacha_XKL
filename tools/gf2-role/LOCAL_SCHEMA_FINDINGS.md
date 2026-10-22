# 本地角色与武器属性 Schema 研究

日期：2026-10-18。所有操作仅读取磁盘文件；未加载或执行游戏程序集、未访问游戏进程、未联网。

## 一手来源与复现

- 当前程序集：[StaticTable.dll.bytes](<D:/GF2Exilium/GF2 Game/GF2_Exilium_Data/LocalCache/Data/ClientRes_Windows/4.0.5136/Codes/StaticTable.dll.bytes>)，客户端资源版本 `4.0.5136`。
- 当前程序集大小为 `15,187,968` 字节，SHA-256 为 `40bc5467af1402674c9545140e05fe6f6afcbda5373dc95d325a190cbbab771c`。
- 当前表目录：[Table](<D:/GF2Exilium/GF2 Game/GF2_Exilium_Data/LocalCache/Data/Table>)。
- 只读元数据提取程序：[schema_metadata/Program.cs](schema_metadata/Program.cs)，使用 .NET `System.Reflection.Metadata` 和 `PEReader`，不使用 `Assembly.Load`。
- 完整常量观测：[schema_constants.jsonl](../../logs/catalog_probe_20261018/schema_constants.jsonl)；精简的权威属性 schema：[verified_property_schema.json](../../logs/catalog_probe_20261018/verified_property_schema.json)。后者保留 111 个 `PropertyData` 字段常量、65 个 `EnemyBalanceData` 字段常量和完整 `DevelopProperty` 枚举。

复现命令：

```powershell
dotnet run --project tools/gf2-role/schema_metadata -- 'D:/GF2Exilium/GF2 Game/GF2_Exilium_Data/LocalCache/Data/ClientRes_Windows/4.0.5136/Codes/StaticTable.dll.bytes' --constants
```

表文件解析沿用 [assist_report.py](assist_report.py) 的 `table_rows`：首个 uint32 为目录头偏移，再跳过 4 字节，对剩余 protobuf 的重复 field 1 解码；每行 field 1 为 ID。

## 已由当前程序集直接证明的属性字段

`GF2.Data.PropertyData` 未混淆，字段名称和 protobuf 字段号可直接读出，不依赖数值猜测。

| protobuf 字段号 | 元数据字段名 | 含义 |
|---|---|---|
| 1 | Id | 属性配置 ID |
| 2 | Pow | 攻击 |
| 3 | MaxHp | 生命上限 |
| 4 | MaxShieldHp | 护盾生命上限 |
| 5 | ShieldArmor | 防御 |
| 6 | ShieldDamage | 稳态伤害相关值 |
| 7 | MaxAp | 行动力原始值 |
| 8 | MaxWillValue | 稳态指数 |
| 9 | Crit | 暴击率原始值 |
| 10 | CritMult | 暴击伤害原始值 |
| 29 | PowPercent | 攻击百分比修正 |
| 30 | MaxHpPercent | 生命百分比修正 |
| 32 | ShieldArmorPercent | 防御百分比修正 |

“含义”为客户端字段命名对应的解释；行动力与百分比如何格式化、等级倍率如何应用，仍需客户端算法证据。不能只凭字段名把原始值直接显示为最终面板。

## 属性类型代码与 protobuf 字段号必须分开

同一当前程序集保留了 `GF2.Data.DevelopProperty` 枚举。枚举值用于属性类型编码，不等于 `PropertyData` 的字段号。

| 属性 | DevelopProperty 枚举值 | PropertyData 字段号 |
|---|---:|---:|
| 攻击 Pow | 1 | 2 |
| 生命 MaxHp | 2 | 3 |
| 防御 ShieldArmor | 4 | 5 |
| 行动力 MaxAp | 6 | 7 |
| 稳态 MaxWillValue | 8 | 8 |
| 暴击率 Crit | 9 | 9 |
| 暴击伤害 CritMult | 10 | 10 |
| 攻击百分比 PowPercent | 29 | 29 |
| 生命百分比 MaxHpPercent | 30 | 30 |
| 防御百分比 ShieldArmorPercent | 33 | 32 |

来源是上述当前程序集的字段 Constant 元数据，不是 Wiki 或旧版程序集。此枚举提供了为词条类型解释命名的依据；具体表/协议字段是否使用该枚举，仍须沿字段关系验证。

## 当前表中的直接数值证据

在 `PropertyData.bytes` 中，行 `11085` 的原始字段为：

```text
f1=11085 f2=87 f3=246 f5=67 f7=900 f8=10
f9=200 f10=1200 f15=50 f24=2 f51=6 f54=3
f55=1000 f68=600 f75=1
```

与本次主调查的 `GunData[1085].f40=11085` 关联后，可确认为针的基础属性配置：攻击 87、生命 246、防御 67，行动力原始值 900、稳态指数 10、暴击原始值 200、暴击伤害原始值 1200。此处不是声称 60 级最终属性。

`GunWeaponData[10853].f21=41223`，而 `PropertyData[41223]` 为：

```text
f1=41223 f2=50 f10=250
```

因此天鹅之死的基础属性配置可以本地关联到攻击 50、暴击伤害原始值 250。50 不是此前 Wiki 显示的 60 级攻击 348。250 若要呈现为 25%，应明确百分比单位/分母的证据来源；此研究记录仅确认原始字段。

`GunLevelExpData[60].f4=100060`，对应 `PropertyData[100060]` 的 f2/f3/f5 为 6950，其他相关倍率项为 1000；该关联由本次主调查读本地表确认。它为等级成长提供配置线索，但仅凭这些数值不能断言完整计算公式、取整顺序及突破加成。

`LevelPropertyData` 当前解出 151,980 行。示例行 `402308070` 是 `{f1:402308070, f11:402308, f12:70, f13:402308070}`。这展示了等级/属性配置的索引形态，但未找到它与针/天鹅之死的直接关联，不应将此表硬套到角色武器成长。

## 已确定的静态解析边界

- 当前程序集大部分行类型、字段及属性名称被混淆；仅反射类名等部分名称保留。
- `GF2.Data.GunReflection` 的 `.cctor` 在元数据中的 RVA 为 0，无可读取 IL；`get_Descriptor` 的 6 字节内容为 `4F531F303313`，不是可按标准 CIL 调用序列解释的正常 descriptor 初始化。记录在 [schema_probe.jsonl](../../logs/catalog_probe_20261018/schema_probe.jsonl)。因此此前扫描 `.cctor` 的 `ldstr` 没有结果，并不代表不存在配置数据。
- StreamingAssets 中的旧版 7 MB 程序集也有相同保护表现；它只能辅助对照，不能作为当前版本字段权威。
- REA 的 `inspect_managed_members` 与 `inspect_managed_artifact` 已各出现一次 64 MB metadata 预算失败；没有再次调用。此前 `Assembly.Load/GetTypes` 缺 `Google.Protobuf` 的路径也没有重试。
- 本次通过静态 metadata reader 绕开上述加载依赖和预算问题；仍未恢复混淆字段的完整官方命名。`GunData`、`GunWeaponData`、`BattleSkillDisplayData`、`TalentKeyData` 的业务字段必须结合本地记录及交叉引用验证，不可把推测描述为程序集 schema 事实。

## 可以继续使用的本地链路

主调查已沿本地表验证以下链路；这些是表数据关系证据，区别于上面程序集直接保留的字段名：

- `GunData[1085].f40 -> PropertyData[11085]`：针基础属性。
- `GunWeaponData[10853].f21 -> PropertyData[41223]`：天鹅之死基础属性。
- `WeaponBreakData.f2=10853`、f3 为技能等级 1～6、f4 指向 `BattleSkillDisplayData[5108531..5108536]`：武器技能各级说明。
- `TalentKeyData` 的 f9 或 f15 关联角色 ID，f6 关联 `BattleSkillDisplayData`；针共键 `901085` 的 f5=8001048、f6=10850907，契合键 `911085` 的 f5=8200068。f5 是否总为 PropertyData 引用须逐表复核。

应优先使用这些已经建立的本地引用关系导出资料，而非继续尝试执行受保护程序集。
