#!/usr/bin/env python3
"""生成官网截图用的假账号数据（不含任何真实账号）。

输出 `tools/site-shots/fake-accounts.json`，由截图脚本 push 到模拟器 App 私有目录。
数据规则与 App 实际存储一致（见 XKL_android/.../AccountStore.kt）：

  { "current": "<uid>",
    "accounts": [
      { "uid": "...", "channel": 5, "phone": "...", "token": "...",
        "tokenSavedAt": 0, "recordsUpdatedAt": <epoch>,
        "records": { "3": [ {"pool_id":261001,"item":1034,"time":...,"item_num":1} ] } } ] }

记录字段使用官方接口原始字段名（pool_id / item / time / item_num）。
五星 item 取 json/ssr.json，非五星 item 取 json/non_ssr.json —— 必须严格分开，
否则 App 会把普通记录也算成五星（上一版脚本就踩过这个坑）。
"""
import json
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SSR = json.loads((ROOT / "json" / "ssr.json").read_text(encoding="utf-8"))
NON_SSR = json.loads((ROOT / "json" / "non_ssr.json").read_text(encoding="utf-8"))

CHAR_SSR = {int(k): v for k, v in SSR["SSR_character"].items()}
WEAPON_SSR = {int(k): v for k, v in SSR["SSR_weapon"].items()}
PERM_SSR = {int(k): v for k, v in SSR["SSR_permanent"].items()}
PERM_CHARS = [k for k in PERM_SSR if len(str(k)) == 4]
PERM_WEAPONS = [k for k in PERM_SSR if len(str(k)) == 5]
LIMITED_CHARS = [k for k in CHAR_SSR if k not in PERM_SSR]
LIMITED_WEAPONS = [k for k in WEAPON_SSR if k not in PERM_SSR]

FILLER_CHARS = [int(k) for k in NON_SSR["SR_character"]]
FILLER_WEAPONS = [int(k) for k in NON_SSR["SR_weapon"]] + [int(k) for k in NON_SSR["R_weapon"]]

ALL_SSR = set(CHAR_SSR) | set(WEAPON_SSR) | set(PERM_SSR)
assert not (set(FILLER_CHARS) & ALL_SSR), "普通角色 id 与五星表重叠"
assert not (set(FILLER_WEAPONS) & ALL_SSR), "普通武器 id 与五星表重叠"

POOL_IDS = {1: 261001, 3: 261003, 4: 261004, 6: 261006, 7: 261007}


def make_pool(pool_type, total, hits, start_time, step=211):
    """按「垫抽 -> 五星 -> 垫抽」的顺序造一条完整的抽卡记录。

    hits: [(第几抽出货, item_id), ...]，出货序号按 1 开始计数。
    """
    is_weapon_pool = pool_type in (4, 7)
    filler = FILLER_WEAPONS if is_weapon_pool else FILLER_CHARS
    records = []
    hit_at = {draw: item for draw, item in hits}
    t = start_time
    for draw in range(1, total + 1):
        item = hit_at.get(draw, random.choice(filler))
        records.append({
            "pool_id": POOL_IDS[pool_type],
            "item": item,
            "time": t,
            "item_num": 1,
        })
        t += step + random.randint(0, 90)
    return records


def main():
    random.seed(20261022)
    now = int(time.time())
    day = 86400

    char_a, char_b, char_c = LIMITED_CHARS[0], LIMITED_CHARS[7], LIMITED_CHARS[12]
    weapon_a, weapon_b = LIMITED_WEAPONS[0], LIMITED_WEAPONS[7]
    perm_char_a, perm_char_b = PERM_CHARS[0], PERM_CHARS[1]
    perm_weapon = PERM_WEAPONS[0]

    account_one = {
        "uid": "389123920",
        "channel": 5,
        "phone": "13800000000",
        # 只是为了让界面显示「凭证有效」，截图环境不会真的去刷新
        "token": "FAKE.c2NyZWVuc2hvdC1vbmx5LXRva2Vu",
        "tokenSavedAt": now - 5 * day,
        "recordsUpdatedAt": now - 3600,
        "records": {
            # 角色池：268 抽 5 个五星，其中两个常驻 -> 歪 2
            "3": make_pool(
                3,
                268,
                [(58, char_a), (132, char_b), (198, char_c), (236, perm_char_a), (262, perm_char_b)],
                now - 26 * day,
            ),
            # 武器池：120 抽 3 个五星，其中一个常驻 -> 歪 1
            "4": make_pool(4, 120, [(47, weapon_a), (96, weapon_b), (118, perm_weapon)], now - 18 * day),
            # 常驻池：90 抽 2 个五星
            "1": make_pool(1, 90, [(63, perm_char_a), (88, perm_char_b)], now - 10 * day),
            # 自选角色池：44 抽，还没出金（垫 44）
            "6": make_pool(6, 44, [], now - 4 * day),
            # 自选武器池：20 抽，垫 20
            "7": make_pool(7, 20, [], now - 2 * day),
        },
    }

    account_two = {
        "uid": "512345678",
        "channel": 5,
        "phone": "13900000000",
        "token": "FAKE.c2NyZWVuc2hvdC1vbmx5LXRva2VuLTI",
        "tokenSavedAt": now - 3 * day,
        "recordsUpdatedAt": now - 2 * day,
        "records": {
            "3": make_pool(3, 35, [(35, char_b)], now - 3 * day),
        },
    }

    data = {"current": account_one["uid"], "accounts": [account_one, account_two]}
    out = ROOT / "tools" / "site-shots" / "fake-accounts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    counts = {p: len(r) for p, r in account_one["records"].items()}
    ssr_counts = {
        p: sum(1 for row in rows if row["item"] in ALL_SSR) for p, rows in account_one["records"].items()
    }
    total = sum(counts.values())
    print(f"written {out} ({out.stat().st_size} bytes) pools={counts} ssr={ssr_counts} total={total}")


if __name__ == "__main__":
    main()
