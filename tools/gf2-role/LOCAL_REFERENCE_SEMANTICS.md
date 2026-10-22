# 本地动态 Buff 引用的语义与客户端调用证据

日期：2026-10-18。只读本地磁盘，不访问网络、不执行游戏代码、不访问游戏进程。Wiki 名称只用作追踪目标，不是本报告的数据来源。

## 结论

`0:-1,组ID,序号` 不能当作 `BattleBuffPerformData[组ID]`。本地的 `BuffShareLimitByGroupData` / `BuffShareLimitData` 保存了按角色 grade 切换的 Buff 列表。多个目标名称存在于这些列表对应的本地 Buff 显示记录中。

客户端 Lua 进一步证明：角色技能格式化接受 **当前/预览角色 grade 的技能详情对象**，因此一条静态技能显示记录不能总是还原唯一的最终 Buff 名称和描述。应导出 grade 分支，或要求调用方传入 grade；不可统一选择最高分支。

没有在本次 Lua 集合中找到 `-1` 或序号的底层解析函数，尚不能把序号的 1-based 解释、`-N` 后缀含义、grade 缺省/回退逻辑称为“已恢复客户端算法”。它们目前由本地数据结构及交叉引用支持。

## BuffShareLimit 表的直接证据

表目录：`D:/GF2Exilium/GF2 Game/GF2_Exilium_Data/LocalCache/Data/Table`。

已直接读出：`BuffShareLimitByGroupData[组ID].f2` 指向 `BuffShareLimitData` 的行 ID；目标例子的两者 ID 相同，实际解析不能依赖恰好相同。

`BuffShareLimitData.f4` 和 `.f5` 都是 UTF-8 字符串。f4 是逗号分隔的 grade ID；f5 是一一对应的逗号分隔列表；同一项内分号分隔 Buff，部分 ID 有 `-N` 后缀。

`0:-1,组ID,第三参数` 中，第三参数应解释为该 grade 列表中 **从 1 开始的 Buff 槽位序号**，不是技能等级/rank。交叉验证例子：`0:-1,103209,1` 指向第一项 `10320981`（校音），`0:-1,10370401,2` 指向第二项 `103704016-2` 的 Buff ID `103704016`（迷彩）。grade 来自另一个上下文维度，不能拿第三参数去选 grade。这里的解释是本地表结构与显示记录交叉验证得出，尚非反编译得到的分支语句。

| 组 ID | grade ID | 对应 f5 项 |
|---|---|---|
| 103209 | 103201 | `10320981;10320991-10` |
| 103209 | 103204 | `10320981;10320992-10` |
| 10370401 | 103701 | `103704014;103704016-2` |
| 10370401 | 103707 | `103704034;103704036-1` |
| 104700 | 104701～104703 | `104704011-1` |
| 104700 | 104704～104705 | `104704021-1` |
| 104700 | 104706 | `104704031-1` |
| 104700 | 104707 | `104704041-1` |
| 10770800 | 107701 | `107708004-1` |
| 10770800 | 107702～107707 | `107708005-1` |
| 10780401 | 107801～107803 | `107804010-1` |
| 10780401 | 107804～107806 | `107804020-1` |
| 10780401 | 107807 | `107804030-1` |

复现：

```powershell
python tools/gf2-role/local_catalog_probe.py row BuffShareLimitByGroupData 103209 10370401 104700 10770800 10780401
python tools/gf2-role/local_catalog_probe.py row BuffShareLimitData 103209 10370401 104700 10770800 10780401
```

## Lua 的一手调用证据

本地 Lua 资源目录：`D:/GF2Exilium/GF2 Game/GF2_Exilium_Data/LocalCache/Data/ClientRes_Windows/4.0.5136/A5CFF04BAF8EAC27EF4D4716C075F344`，本次扫描 1,031 个文件、7,808,861 字节。

文件为 XOR `0xFF` 编码，解码后是标准 **Lua 5.3**（`1B 4C 75 61 53`），不是 LuaJIT。本次新增只读解析器 `read_lua53.py`，读取原始 source、行号、局部变量、常量和指令，不执行字节码。原有 `luajit_disasm.py` 在这版资源上会报格式不符，不能用它的输出判断源码不存在。

以下 Lua 风格代码是从指令恢复的等价调用，**不是声称已获取明文源码**。原始 source 路径来自字节码调试信息。

### 角色技能主说明与预览

资源：`B8A371B32EE025568560BDF989B75474.bytes`。

原始 source：`UI/FacilityBarrackPanel/Content/UIChrSkillInfoDialog.lua`。

第 155～156 行（PC 63～73）：

```lua
local skillDetialInfo = self.gunCmdData:GetPreviewGunUpGradeSkillDetialInfo(self.curGunGradeId)
local tmpDesc = self.gunCmdData:FormatSkillDesc(self.skillData.id, nil, skillDetialInfo)
```

同一文件第 316～317 行（PC 60～72）：

```lua
local skillDetialInfo = self.gunCmdData:GetPreviewGunUpGradeSkillDetialInfo(self.curGunGradeId)
local tmpDesc = self.gunCmdData:FormatSkillDesc(
    self.skillData.id, self.skillDisplayData.DescriptionBrief.str, skillDetialInfo)
```

这里 grade 是显式输入，且详情对象传入格式化器，直接支持“描述会随 grade 分支变化”的实现判断。

### 角色技能升级说明

资源：`447B924D054BA0FFE5065CC4DC266A21.bytes`。

原始 source：`UI/FacilityBarrackPanel/Item/UISkillDetailItem.lua`。

第 63～64 行（PC 58～68）：

```lua
local skillDetialInfo = self.gunCmdData:GetPreviewGunSkillDetialInfoBySkillId(skillData.id)
local tmpDesc = self.gunCmdData:FormatSkillDesc(
    skillData.id, skillData.upgrade_description.str, skillDetialInfo)
```

### 武器说明

资源：`3C15612B43F989BAB7FA980304A3B4F6.bytes`。

原始 source：`UI/WeaponPanel/WeaponV4/UIChrSpecialEffectDialog.lua` 第 128 行：

```lua
local skillDes = self.weaponCmdData:FormatSkillDesc(weaponSkillDatas[i].id)
```

另外 `1F66C898047276A92EFD4B69B72D05C4.bytes` 和 `DC16031DAB9D0771E5EA3EA3A2A26D42.bytes` 也调用武器 `FormatSkillDesc`。

原始解析证据：`logs/catalog_probe_20261018/lua_format_skill_calls.json`、`lua_special_effect.json`。它们包含调用所在函数的全部常量和指令。

## 已确认的边界

- 1,031 个文件解码后的字面量中，`FormatSkillDesc` 只出现于上述 5 个 UI 模块（忽略 Lua 文件注册索引）；没有 `BuffShare*`、`BuffClassData` 或 `GetBuffClass` 字符串。
- 上述 Lua 实际把工作交给 `gunCmdData` / `weaponCmdData` 方法；本次没有恢复这些方法体。
- 当前 `Assembly-CSharp.dll.bytes`、`Common.dll.bytes` 和 `CommonUtils.dll.bytes` 中未发现这几个方法名的明文 ASCII 标识符。此项只说明标识符搜索没有命中，不能推断方法不存在。
- 没有重试 REA 64 MB 预算失败路径，也没有通过 `Assembly.Load` 或 `GetTypes` 加载游戏程序集。
- `0:ID,等级` 是否使用相同的组查找、等级的确切选择规则，需要独立验证；不能自动把所有 `0:` 引用都套进同一分支算法。

建议导出的状态区分：`local-direct`（直接显示记录）、`local-grade-variants`（按本地表保存所有分支）、`unresolved`（不足以唯一解析）。每个结果保留原始引用、group 行、grade ID、Buff 原始串和最终显示行路径，避免 Wiki 文本或推测悄悄进入本地数据。
