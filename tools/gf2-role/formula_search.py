"""Search for a panel formula consistent across all three known samples.

Inputs per character: wiki level-60 base attack, wiki weapon attack at level
60, decoded affix totals, and the user-supplied panel value.
"""

from __future__ import annotations

import itertools
import json
import re
import sys

SAMPLES = [
    {
        "name": "埃芙", "base": 757, "weapon": 348, "panel": 3206,
        "affix": {1: 108, 4: 152, 6: 64, 9: 170, 10: 50, 19: 1160, 21: 140,
                  23: 416, 29: 136, 33: 30},
    },
    {
        "name": "威玛西娜", "base": 844, "weapon": 390, "panel": 4126,
        "affix": {1: 89, 9: 170, 10: 50, 19: 464, 21: 440, 23: 1772, 29: 136},
    },
    {
        "name": "克莱妲", "base": 767, "weapon": 362, "panel": 4385,
        "affix": {1: 96, 9: 200, 10: 50, 23: 2704, 29: 152},
    },
]


def candidate_inputs(sample: dict) -> dict:
    affix = sample["affix"]
    raw = {f"a{t}": v for t, v in affix.items()}
    scaled = {f"a{t}/10": v / 10 for t, v in affix.items()}
    scaled.update({f"a{t}/100": v / 100 for t, v in affix.items()})
    return {
        "base": float(sample["base"]),
        "weapon": float(sample["weapon"]),
        "panel": float(sample["panel"]),
        **raw,
        **scaled,
    }


def main() -> int:
    keys = ["base", "weapon", "a1", "a29", "a9", "a10"]
    scales = [1.0, 0.1, 0.01]
    hits = []
    for combo in itertools.permutations(keys, 2):
        for scale in scales:
            for op in ("+", "*", "-", "/"):
                values = []
                ok = True
                for sample in SAMPLES:
                    env = candidate_inputs(sample)
                    left, right = env[combo[0]], env[combo[1]] * scale
                    if op == "+":
                        value = left + right
                    elif op == "-":
                        value = left - right
                    elif op == "*":
                        value = left * right
                    else:
                        if right == 0:
                            ok = False
                            break
                        value = left / right
                    values.append(value)
                if not ok:
                    continue
                diffs = [v - s["panel"] for v, s in zip(values, SAMPLES)]
                spread = max(diffs) - min(diffs)
                if spread < 60:
                    hits.append((spread, combo, scale, op, [round(d, 1) for d in diffs]))
    hits.sort()
    print("closest two-term forms (spread < 60):")
    for spread, combo, scale, op, diffs in hits[:25]:
        print(f"  {combo[0]} {op} ({scale:g}*{combo[1]}): spread={spread:.1f} diffs={diffs}")
    if not hits:
        print("  none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
