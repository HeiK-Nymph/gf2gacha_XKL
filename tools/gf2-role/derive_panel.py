"""Constraint search for the panel stat formula.

Uses two accounts that expose the same character with the same weapon at
level 60 but different mods. One account has user-supplied panel values, the
other only combat power. The search tests linear and multiplicative
combinations of decoded affix totals against the known panel values.
"""

from __future__ import annotations

import argparse
import collections
import itertools
import json
from pathlib import Path

PANELS = {
    "1065": {"attack": 3206, "defense": 1336, "crit": 59.4, "critDamage": 161.8},
    "1066": {"attack": 4126, "defense": 1311, "crit": 84.1, "critDamage": 178.3},
    "1079": {"attack": 4385, "defense": 1296, "crit": 109.5, "critDamage": 164.5},
}


def totals_by_character(path: Path, account: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for character in data:
        key = f"{account}:{character['role']['id']}"
        totals: collections.Counter = collections.Counter()
        for mod in character["mods"]:
            for slot in mod["slots"]:
                for lane in slot["lanes"]:
                    totals[lane["type"]] += lane["amount"]
        out[key] = {
            "totals": dict(totals),
            "power": character["role"]["combatPower"],
            "weapon": [w["configId"] for w in character["weapons"]],
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-panel", required=True, help="correlate json for the account with known panels")
    ap.add_argument("--with-power", required=True, help="correlate json for the comparison account")
    ap.add_argument("--out")
    args = ap.parse_args()

    with_panel = totals_by_character(Path(args.with_panel), "panel")
    with_power = totals_by_character(Path(args.with_power), "power")

    report = {"panelAccount": with_panel, "powerAccount": with_power}

    # Same character, same weapon, different mods: the difference in a stat is
    # fully explained by the affine combination of affix totals.
    comparisons = []
    for key, entry in with_panel.items():
        character_id = key.split(":")[1]
        other_key = f"power:{character_id}"
        other = with_power.get(other_key)
        if not other or other["weapon"] != entry["weapon"]:
            continue
        stats = {}
        for stat, combat in entry["totals"].items():
            stats[stat] = {"withPanel": combat, "withPower": other["totals"].get(stat, 0),
                           "delta": combat - other["totals"].get(stat, 0)}
        comparisons.append({
            "character": character_id,
            "panelValues": PANELS.get(character_id),
            "powerPanelAccount": entry["power"],
            "powerOtherAccount": other["power"],
            "affixDelta": stats,
        })
    report["comparisons"] = comparisons

    # Fit attack as base + sum(weight_t * total_t) over the three panel samples.
    # Solve using least squares over candidate single-type and two-type models.
    samples = []
    for key, entry in with_panel.items():
        character_id = key.split(":")[1]
        panel = PANELS.get(character_id)
        if panel:
            samples.append((entry["totals"], panel))

    results = []
    for size in (1, 2, 3):
        for combo in itertools.combinations([1, 3, 9, 10, 29, 30, 33], size):
            # straight sum model: attack = c0 + sum(total_t)
            rows = [[1.0] + [entry.get(t, 0) for t in combo] for entry, _ in samples]
            targets = [panel["attack"] for _, panel in samples]
            solution = solve(rows, targets)
            if solution is None:
                continue
            residual = max(abs(sum(r[i] * solution[i] for i in range(len(solution))) - t)
                           for r, t in zip(rows, targets))
            results.append({"types": list(combo), "coefficients": solution, "maxResidual": residual})
    results.sort(key=lambda item: item["maxResidual"])
    report["attackFits"] = results[:10]

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


def solve(rows, targets):
    """Solve a small dense linear system by Gaussian elimination."""
    n = len(rows[0])
    m = len(rows)
    if m < n:
        return None
    matrix = [list(row) + [target] for row, target in zip(rows, targets)]
    for col in range(n):
        pivot = None
        for row in range(col, m):
            if abs(matrix[row][col]) > 1e-9:
                pivot = row
                break
        if pivot is None:
            return None
        matrix[col], matrix[pivot] = matrix[pivot], matrix[col]
        factor = matrix[col][col]
        for i in range(col, n + 1):
            matrix[col][i] /= factor
        for row in range(m):
            if row == col:
                continue
            factor = matrix[row][col]
            if abs(factor) < 1e-12:
                continue
            for i in range(col, n + 1):
                matrix[row][i] -= factor * matrix[col][i]
    return [matrix[i][n] for i in range(n)]


if __name__ == "__main__":
    raise SystemExit(main())
