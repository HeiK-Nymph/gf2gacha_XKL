# GF2 panel investigation status

Updated 2026-10-18.

## Confirmed

* A fresh game login can be captured and replayed on an independent TCP
  connection. The first replay may be refused with command `19900`
  (field 1 = 44564, field 2 = signed -95985); an immediate retry succeeds.
* `10428(4382210)` returned a matching `10429` (response UID verified). The
  full assist snapshot is stored at
  `logs/role_capture_20261018/assist-4382210.bin`.
* Characters in that response: 1065 (power 21340), 1066 (power 23661),
  1079 (power 27444) - matching the user's screenshots.
* The panel numbers are not carried in the response. Full recursive scan for
  attack/defense/crit/crit-damage across float32, float64, int32/int16 at
  scales 1/10/100/1000/10000, and wire-level fixed fields, finds nothing.
* Weapon mod affix lanes decode as (type, amount) pairs. Types 4, 5, 6, 19,
  21, 22, 23 have every amount >= 64 and are calibration markers, not stats.
  Real stat types observed: 1, 9, 10, 29, 30, 33.

## Correlations

Totals per character versus the user-supplied panels:

| id | type 1 | type 9 | type 10 | type 29 | type 33 | panel attack | panel defense |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1065 | 108 | 170 | 50 | 136 | 30 | 3206 | 1336 |
| 1066 | 89 | 170 | 50 | 136 | 0 | 4126 | 1311 |
| 1079 | 96 | 200 | 50 | 152 | 0 | 4385 | 1296 |

* `type 29` correlates with combat power ordering (136, 136, 152).
* `type 33` appears only on the first character and equals a likely defense
  component, but 30 is far below 1336, so scaling or another source applies.
* The wiki level-60 base values (757/512, 722/577, 837/577) do not exist as
  pairs anywhere in PropertyData / PropertyNewData / LevelPropertyData /
  GunPresetData.

## Cross-account comparison (attempted)

The two archived accounts both contain character 1065, but with different
weapons (10653 in UID 4382210, 11038 in UID 308089), so they are not a clean
same-weapon comparison and the differential solve is void.

## Derived-data limit

## Assist API: final scope (2026-10-18)

`10428(uid) -> 10429` is the assist query. What it actually carries, verified
end to end against UID 4382210:

| Field | Available | Notes |
|---|---|---|
| Character id, name, level, rarity | yes | name resolved from `GunData` + `LangPackageTableCnData` |
| 作战效能 (combat power) | yes | server-computed, matches in-game |
| Weapon name + level | yes | name from `GunWeaponData` field 2 language key |
| Weapon mods (4 per character) | yes | instance ids + config ids |
| Mod affix type + value | yes | 16-bit lanes; values below 64 are stats, 64+ are calibration marks |
| Mod affix stat name | unresolved | type codes do not map cleanly to `LanguagePropertyData` row ids |
| Attack / defense / crit / crit damage | no | not in the response in any encoding; client computes them |
| 心智螺旋 / 契合键 / 共键 bonuses | no | carried in login commands (`11506`, `10131`), not in assist |

### Affix system (verified)

The mod affix type codes are a closed set of 8, and their value ranges come from
`AffixGroupData`, keyed by the affix plan group referenced from `WeaponModData`
field 11 through `AffixPlanIdData`:

| type | value range | notes |
|---:|---|---|
| 1 | 17-24 | plan-dependent; range widens on other plans |
| 2 | 38-54 | |
| 4 | 10-16 | |
| 9 | 35-50 (up to 68) | |
| 10 | 35-50 | only on plans that include it (e.g. 5411) |
| 29 | 26-38 (up to 50) | |
| 30 | 26-38 | |
| 33 | 26-38 | |

Every lane value observed in the 4382210 and 308089 captures falls inside the
corresponding range, which is what makes the decoding trustworthy. Lanes with
values >= 64 are calibration marks, not stats.

The human-readable name for each type code is still unresolved: the codes do not
index `LanguagePropertyData` row ids. `assist_report.py` therefore emits
`nameHint` plus the observed `range`, and consumers should treat `nameHint` as
unconfirmed.

Working report generator: `assist_report.py` turns a 10429 stream into JSON with
character, weapon and mod-affix data. Sample output for 4382210:
`logs/role_capture_20261018/report-4382210.json`.

Consequences for a mini-program feature:

1. Show name / level / combat power / weapon / mod affixes. All offline, no
   formula needed.
2. Panel numbers cannot be reproduced for another player's assist character,
   because the key/spiral bonuses are not part of the assist payload.
3. A fresh game login token is required per query; the token is invalidated
   when the account logs in again (`19900` / `10003`).

`derive_panel.py` fits `attack = c0 + sum(w_t * total_t)` over the three panel
samples. Every two-type model fits exactly; with three data points and three
free coefficients that is expected and carries no information. Single-type
models leave residuals of 259 to 920, so no single affix type explains attack.

The level-60 attack of the equipped weapons (10653 / 10663 / 10793) is not in
the static tables under any obvious key, and the wiki level-60 base values are
not stored as pairs either.

To finish the derivation, two more independent panel samples are needed, or one
controlled experiment: capture the same account with two different weapon-mod
loadouts and compare the two panels. Each new sample adds one constraint; with
five or six samples a single formula should survive and the rest fall away.
