"""从本地游戏表生成 `json/pools.json`（卡池映射），供 R2 下发、微信小程序端消费。

口径（由旧 `json/pools.json` 276 条反推并逐条验证，276/276 完全一致）：
  * `type_id` / `type_name`：GachaData 的 `type` + GachaTypeListData.name
  * `name`：`type` 3（人形UP）/ 4（武器UP）取 **UP 五星的名字**；其他类型取卡池表名
  * `start_time` / `end_time`：表内秒级时间戳；`*_text` 固定按 UTC+8 格式化为
    `YYYY-MM-DD HH:MM:SS`（时间戳为 0 时输出 null，例如常驻池）
  * `up_5` / `up_4`：`gunUpItem`（type 3）/ `weaponUpItem`（type 4）里的 `5:…` / `4:…`
    分组，冒号分隔多个 id；`kind` 由 ItemData.type（20=武器）判定
  * `type` 6 / 7（自选UP）历史上不在文件里，默认跳过，`--include-self-select` 可纳入
  * 旧文件里有、本次表里已没有的卡池 **原样保留**（小程序/历史记录可能仍引用），
    只在 summary 里列为 kept

与旧文件的兼容性由 `--verify-against <旧文件>` 证明：逐条比较，不一致即报错退出。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

CN_TZ = timezone(timedelta(hours=8))
DEFAULT_SKIP_TYPES = (6, 7)  # 自选UP：历史 pools.json 从未收录
OUTPUT_RELATIVE = Path("json") / "pools.json"
PLAYER_LOG_CANDIDATES = (
    Path.home() / "AppData" / "LocalLow" / "SunBorn" / "少女前线2：追放" / "Player.log",
    Path.home() / "AppData" / "LocalLow" / "SunBorn" / "Girls' Frontline 2" / "Player.log",
    Path.home() / "AppData" / "LocalLow" / "SunBorn" / "Girls Frontline 2" / "Player.log",
)
TABLE_FILES = ("GachaData.bytes", "GachaTypeListData.bytes", "ItemData.bytes",
               "LangPackageTableCnData.bytes")


class PoolsError(RuntimeError):
    pass


# ============================================================
# 目录定位
# ============================================================
def repo_root(explicit: Optional[str] = None) -> Path:
    for candidate in (explicit, os.environ.get("GF2GACHA_ROOT"), os.getcwd()):
        if candidate:
            path = Path(candidate).expanduser()
            if (path / "json" / "ssr.json").is_file():
                return path.resolve()
    # 兜底：脚本在 <root>/tools/gf2-pools/ 下
    guess = Path(__file__).resolve().parents[2]
    if (guess / "json" / "ssr.json").is_file():
        return guess
    raise PoolsError("找不到仓库根目录（需要含 json/ssr.json 的目录）")


def table_directory(explicit: Optional[str] = None) -> Path:
    for candidate in (explicit, os.environ.get("GF2_TABLE_DIR")):
        if candidate:
            path = Path(candidate).expanduser()
            if (path / "GachaData.bytes").is_file():
                return path.resolve()
            raise PoolsError(f"指定的表目录里没有 GachaData.bytes：{path}")
    for log_path in PLAYER_LOG_CANDIDATES:
        if not log_path.is_file():
            continue
        match = re.search(r"\[Subsystems\] Discovering subsystems at path (.+?)/UnitySubsystems",
                          log_path.read_text(encoding="utf-8", errors="ignore"))
        if not match:
            continue
        path = Path(match.group(1).strip()) / "LocalCache" / "Data" / "Table"
        if (path / "GachaData.bytes").is_file():
            return path.resolve()
    raise PoolsError("未找到游戏 Table 目录：请设置 GF2_TABLE_DIR 或 --tables")


# ============================================================
# protobuf（复用仓库 backend/pb 的已编译定义，容忍版本不一致）
# ============================================================
def _tolerate_protobuf_version_mismatch() -> None:
    try:
        from google.protobuf import runtime_version
    except Exception:
        return
    if getattr(runtime_version, "_xkl_lenient", False):
        return
    original = runtime_version.ValidateProtobufRuntimeVersion

    def lenient(*args, **kwargs):
        try:
            original(*args, **kwargs)
        except Exception:
            pass

    runtime_version.ValidateProtobufRuntimeVersion = lenient
    runtime_version._xkl_lenient = True


def _load_pb(root: Path):
    pb_dir = root / "backend" / "pb"
    if not pb_dir.is_dir():
        raise PoolsError(f"缺少 protobuf 定义目录：{pb_dir}")
    _tolerate_protobuf_version_mismatch()
    sys.path.insert(0, str(pb_dir))
    import GachaData_pb2 as gacha_pb  # noqa: E402
    import GachaTypeListData_pb2 as type_pb  # noqa: E402
    import ItemData_pb2 as item_pb  # noqa: E402
    import LangPackageTableCnData_pb2 as lang_pb  # noqa: E402
    return gacha_pb, type_pb, item_pb, lang_pb


def _read_table(path: Path, message_class):
    raw = path.read_bytes()
    if len(raw) < 4:
        raise PoolsError(f"表文件过短：{path}")
    head = struct.unpack("<I", raw[:4])[0]
    message = message_class()
    message.ParseFromString(raw[head + 4:])
    return message


# ============================================================
# 卡池记录
# ============================================================
def _parse_up(value: str):
    up5, up4 = [], []
    for group in (value or "").split(","):
        group = group.strip()
        if not group:
            continue
        rank, _, rest = group.partition(":")
        rank = rank.strip()
        if rank not in ("5", "4") or not rest:
            continue
        bucket = up5 if rank == "5" else up4
        for token in rest.split(":"):
            token = token.strip()
            if token.isdigit():
                bucket.append(int(token))
    return up5, up4


def _time_text(timestamp: int) -> Optional[str]:
    return datetime.fromtimestamp(timestamp, CN_TZ).strftime("%Y-%m-%d %H:%M:%S") if timestamp else None


def build_pools(table_dir: Path, root: Path, skip_types=DEFAULT_SKIP_TYPES) -> Dict[str, Any]:
    gacha_pb, type_pb, item_pb, lang_pb = _load_pb(root)
    gacha = _read_table(table_dir / "GachaData.bytes", gacha_pb.GachaData)
    type_table = _read_table(table_dir / "GachaTypeListData.bytes", type_pb.GachaTypeListData)
    item_table = _read_table(table_dir / "ItemData.bytes", item_pb.ItemData)
    lang_table = _read_table(table_dir / "LangPackageTableCnData.bytes", lang_pb.LangPackageTableCnData)

    type_names = {unit.id: unit.name for unit in type_table.Units}
    language = {unit.id: unit.content for unit in lang_table.Units}
    items = {unit.id: unit for unit in item_table.Units}

    def item_record(item_id: int) -> Dict[str, Any]:
        item = items.get(item_id)
        if item is None:
            return {"id": item_id, "name": None, "kind": None}
        name = language.get(item.name.id) if hasattr(item.name, "id") else str(item.name)
        return {"id": item_id, "name": name, "kind": "weapon" if item.type == 20 else "character"}

    pools: Dict[str, Any] = {}
    skipped = []
    for unit in gacha.Units:
        if unit.type in skip_types:
            skipped.append({"id": unit.id, "type_id": unit.type})
            continue
        if unit.type == 3:
            source = unit.gunUpItem
        elif unit.type == 4:
            source = unit.weaponUpItem
        else:
            source = unit.gunUpItem or unit.weaponUpItem
        up5_ids, up4_ids = _parse_up(source)
        up5 = [item_record(i) for i in up5_ids]
        table_name = language.get(unit.name.id)
        display_name = up5[0]["name"] if unit.type in (3, 4) and up5 and up5[0]["name"] else table_name
        pools[str(unit.id)] = {
            "type_id": unit.type,
            "type_name": type_names.get(unit.type),
            "name": display_name,
            "start_time": unit.startTime,
            "end_time": unit.endTime,
            "start_time_text": _time_text(unit.startTime),
            "end_time_text": _time_text(unit.endTime),
            "up_5": up5,
            "up_4": [item_record(i) for i in up4_ids],
        }
    return {"pools": pools, "skipped": skipped}


def _ordered(pools: Dict[str, Any]) -> Dict[str, Any]:
    return dict(sorted(pools.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0))


def write_pools(path: Path, pools: Dict[str, Any]) -> int:
    payload = json.dumps(_ordered(pools), ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(pending, path)
    return len(payload.encode("utf-8"))


def verify_against(path: Path, pools: Dict[str, Any]) -> Dict[str, Any]:
    old = json.loads(path.read_text(encoding="utf-8"))
    added = [k for k in pools if k not in old]
    missing = [k for k in old if k not in pools]
    changed = []
    for key, value in old.items():
        if key in pools and pools[key] != value:
            changed.append({"id": key, "delta": {k: {"old": value.get(k), "new": pools[key].get(k)}
                                                 for k in set(value) | set(pools[key])
                                                 if value.get(k) != pools[key].get(k)}})
    return {"compared": len(old), "unchanged": len(old) - len(missing) - len(changed),
            "added": added, "missing": missing, "changed": changed}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="从本地游戏表生成 json/pools.json")
    parser.add_argument("--tables", help="游戏 Table 目录（默认 GF2_TABLE_DIR 或 Player.log 自动定位）")
    parser.add_argument("--root", help="仓库根目录（默认 GF2GACHA_ROOT / cwd）")
    parser.add_argument("--output", help="输出文件（默认 <root>/json/pools.json）")
    parser.add_argument("--include-self-select", action="store_true",
                        help="同时收录 type 6/7 自选UP（历史 pools.json 未包含）")
    parser.add_argument("--verify-against", help="与给定旧 pools.json 逐条比较，不一致即失败")
    parser.add_argument("--keep-removed", action="store_true", default=True,
                        help="保留旧文件里本次表已没有的卡池（默认开启）")
    args = parser.parse_args(argv)

    try:
        root = repo_root(args.root)
        table_dir = table_directory(args.tables)
        skip = () if args.include_self_select else DEFAULT_SKIP_TYPES
        built = build_pools(table_dir, root, skip_types=skip)
        pools = built["pools"]
        output = Path(args.output).expanduser() if args.output else root / OUTPUT_RELATIVE
        if not output.is_absolute():
            output = (root / output).resolve()

        verification = None
        if args.verify_against:
            verification = verify_against(Path(args.verify_against), pools)

        kept = []
        if output.is_file() and args.keep_removed:
            previous = json.loads(output.read_text(encoding="utf-8"))
            for key, value in previous.items():
                if key not in pools:
                    pools[key] = value
                    kept.append(key)

        size = write_pools(output, pools)
        by_type: Dict[str, int] = {}
        for pool in pools.values():
            by_type[str(pool["type_id"])] = by_type.get(str(pool["type_id"]), 0) + 1
        summary = {
            "output": str(output),
            "pools": len(pools),
            "by_type": dict(sorted(by_type.items(), key=lambda kv: int(kv[0]))),
            "bytes": size,
            "table_dir": str(table_dir),
            "skipped_self_select": len(built["skipped"]),
            "kept_from_previous": kept,
            "verification": verification,
        }
        print(json.dumps(summary, ensure_ascii=False))
        if verification:
            if verification["changed"] or verification["missing"]:
                raise PoolsError("与旧 pools.json 不一致："
                                 f"changed={len(verification['changed'])} missing={verification['missing'][:5]}")
        return 0
    except PoolsError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:  # 解析/IO 异常一律显式失败，不回退旧文件
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
