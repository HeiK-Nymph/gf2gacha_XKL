# 图鉴描述数据

`catalog.json` 根据现有 `ssr.json`、`non_ssr.json` 的 ID 名单，从本地游戏表生成。现有名单仍用于分类、筛选和显示顺序，图鉴详情按相同 ID 查询。

## 按已有 JSON 的 ID 查询

```js
const id = '1085' // 来自 ssr.SSR_character、ssr.SSR_permanent 或其他已有分组
const item = catalog.items[id]

item.name        // 针
item.type        // character；武器为 weapon
item.description // 角色或武器简介
```

同一种取法适用于 `SSR_character`、`SSR_weapon`、`SSR_permanent`、`SR_character`、`SR_weapon`、`R_weapon` 的所有 ID。全部 ID、引用 ID、椎体 ID 都保存为字符串。

## 顶层字段

| 字段 | 内容 |
|---|---|
| `schemaVersion` | 当前结构版本，现为 `1` |
| `source` | `local-game-tables`，内容来自本地游戏表 |
| `items[id]` | 角色或武器详情 |
| `skills[id]` | 技能各等级的描述、升级说明、关联效果 |
| `buffs[id]` | Buff/状态的名称和说明 |
| `terms[id]` | 战斗术语、附属技能解释 |

## 角色字段

`items[id].type === 'character'`：

| 字段 | 内容 |
|---|---|
| `id` / `name` / `rarity` | ID、名称、星级 |
| `description` / `quote` / `weaponQuote` | 简介、语录、武器语录 |
| `duty` / `weaponType` | 定位、武器类别 |
| `model` / `weaponName` / `organization` | 型号、档案武器名称、所属组织 |
| `voiceActors.zh` / `voiceActors.ja` | 中文、日文声优 |
| `normalAttackSkillId` | 普攻 ID，查询 `skills` |
| `grades[]` | 椎体阶层；`rank` 为0～6，`id` 是实际椎体 ID |
| `grades[].skillIds` | 该阶层配置的新增/替换技能 ID；不是每阶完整可用技能列表 |
| `grades[].specialSkillIds` | 可展示的特殊技能 ID，例如斩域技能 |
| `talents[]` | 固键、共键、契合键、跃键等；包含 `name`、`category`、可直接显示的 `description`、可选 `skillId`、属性加成 `bonuses` |

```js
const doll = catalog.items['1085']
const attack = catalog.skills[doll.normalAttackSkillId]
const baseSkills = doll.grades[0].skillIds.map(id => catalog.skills[id])
const talentDescriptions = doll.talents.map(t => ({
  name: t.name,
  description: t.description
}))
```

`talents[].bonuses` 只表示词条本身的加成，例如 `{ stat: 'critMult', label: '暴击伤害', value: 3, unit: '%' }`；没有计算玩家最终属性。

## 武器字段

`items[id].type === 'weapon'`：

| 字段 | 内容 |
|---|---|
| `id` / `name` / `rarity` / `description` | ID、名称、星级、简介 |
| `weaponType` / `iconResource` | 武器类别、游戏内图标资源标识；资源标识不是图片 URL |
| `skillLevels[]` | `level` 为技能等级，`skillId` 查询 `skills`；没有有效技能的武器为空数组 |
| `traitSkillId` / `traitDescription` | 特质技能 ID及其说明 |
| `imprintSkillId` / `imprintDescription` | 烙印技能 ID及其说明 |

```js
const weapon = catalog.items['10853']
weapon.description
weapon.traitDescription
weapon.imprintDescription

const firstLevel = catalog.skills[weapon.skillLevels[0].skillId]
firstLevel.name        // 执事热忱
firstLevel.description // Lv.1 的完整技能说明
```

不存在的可选技能 ID 为 `null`，对应说明为空字符串。内部空技能不会作为图鉴技能展示。

## 技能描述与效果弹窗

`skills`、`buffs`、`terms` 中每条记录均有 `id`、`name`、`description`、`references`、`gradeDescriptions`。技能还提供 `level`、`typeLabel`、`upgradeDescription`。

普通 `description` 使用动态引用中首个可用椎体分支的名称。有明确椎体时，优先使用 `gradeDescriptions` 中同 ID 的文本。效果说明必须同时按 `references[].variants` 选择对应的具体效果 ID，不能一律使用基础版本或最高版本。

```js
const skill = catalog.skills['10850701'] // 和弦协奏
const gradeId = '108502'                // 针的第一椎体
const text = skill.gradeDescriptions.find(g => g.gradeId === gradeId)?.description
  ?? skill.description

const reference = skill.references.find(r => r.name === '细胞共鸣')
const target = reference.variants.find(v => v.gradeId === gradeId) ?? reference
const effect = catalog[target.collection][target.id]
effect.description // 此椎体对应的细胞共鸣说明
```

`collection` 为 `buffs` 或 `terms`。不同集合的 ID 可能相同，应带上 `collection` 查询。

## 本地更新

```powershell
python tools/gf2-role/build_catalog_json.py
```

生成器读取两份现有名单，校验 ID/名称、解析本地游戏表并覆盖生成 `json/catalog.json`，不访问 Wiki 或网络。可用 `--tables <Table目录>` 指定游戏表目录。构建证据与内部技能诊断写入 `logs/catalog_probe_20261018/catalog_build_report.json`。

此文件只提供图鉴描述和效果关系，没有加入等级成长计算或玩家实际面板数据。
