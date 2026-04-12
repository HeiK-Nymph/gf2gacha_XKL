"""
SSR 表解析模块 - 从游戏本地 .bytes 文件(protobuf) 解析 SSR 数据
完全复刻 Matcha 项目 (D:\myproject\gf2gacha_Matcha\matcha\gf2gacha) preload/init.go 的逻辑

完整流程：
  Player.log -> 游戏路径 -> Table/ -> .bytes文件 -> proto解析 -> SSR表

依赖: protobuf (google.protobuf), grpcio-tools (编译proto用)
"""

import os
import sys
import re
import struct
import json
from pathlib import Path
from typing import Dict, Optional


# ============================================================
# 确保能导入生成的 pb 模块
# ============================================================
def _ensure_pb_imports():
    """将 pb 目录加入 sys.path 以便 import 生成的 _pb2 模块"""
    _pb_dir = Path(__file__).parent / "pb"
    _pb_path = str(_pb_dir)
    if _pb_path not in sys.path:
        sys.path.insert(0, _pb_path)


# ============================================================
# Player.log 解析
# ============================================================
def find_player_log() -> Optional[Path]:
    """查找 Player.log 文件"""
    user_profile = Path(os.environ.get("USERPROFILE", ""))
    possible_paths = [
        user_profile / "AppData" / "LocalLow" / "SunBorn" / "少女前线2：追放" / "Player.log",
        user_profile / "AppData" / "LocalLow" / "SunBorn" / "Girls' Frontline 2" / "Player.log",
        user_profile / "AppData" / "LocalLow" / "SunBorn" / "Girls Frontline 2" / "Player.log",
    ]
    for log_path in possible_paths:
        if log_path.exists():
            return log_path
    return None


def get_table_dir() -> Optional[str]:
    """
    从 Player.log 提取游戏 Table 目录路径
    正则: [Subsystems] Discovering subsystems at path (.+)/UnitySubsystems
    返回: {gameRoot}/LocalCache/Data/Table 或 None
    """
    player_log = find_player_log()
    if player_log is None:
        return None

    content = player_log.read_text(encoding="utf-8", errors="ignore")
    match = re.search(
        r'\[Subsystems\] Discovering subsystems at path (.+)/UnitySubsystems',
        content
    )
    if not match:
        return None

    game_root = match.group(1).strip()
    table_dir = os.path.join(game_root, "LocalCache", "Data", "Table")
    return table_dir


# ============================================================
# .bytes 文件解析
# ============================================================
def parse_bytes_file(file_path: Path, message_class) -> object:
    """
    解析游戏的 .bytes 配置表文件
    文件格式: 前4字节 uint32 LE 头部偏移，后面是 protobuf 数据
    """
    raw = file_path.read_bytes()
    head = struct.unpack('<I', raw[:4])[0]
    proto_data = raw[head + 4:]
    msg = message_class()
    msg.ParseFromString(proto_data)
    return msg


def load_table(table_dir: str, table_name: str, message_class) -> object:
    """加载指定名称的 .bytes 表文件并返回解析后的消息对象"""
    file_path = Path(table_dir) / f"{table_name}.bytes"
    if not file_path.exists():
        raise FileNotFoundError(f"Table file not found: {file_path}")
    return parse_bytes_file(file_path, message_class)


# ============================================================
# 核心映射表构建（复刻 Matcha preload/init.go）
# ============================================================
class SSRTabler:
    """从游戏 Table/*.bytes 构建 LangMap / ItemMap / ItemRankMap 等映射"""

    def __init__(self):
        self.LangMap: Dict[int, str] = {}           # 语言ID -> 中文名
        self.ItemMap: Dict[int, object] = {}         # 道具ID -> ItemDataUnit
        self.UpItemMap: Dict[int, int] = {}          # 卡池ID -> UP道具5星ID
        self.ItemRankMap: Dict[int, Dict[int, int]] = {}  # 卡池ID -> {道具ID -> 星级}

    def load_all(self, table_dir: str):
        """加载4个核心表，构建所有映射"""
        _ensure_pb_imports()

        import LangPackageTableCnData_pb2 as LangPb
        import ItemData_pb2 as ItemPb
        import GachaData_pb2 as GachaPb

        # Step 1: 语言包 -> LangMap
        lang_data: LangPb.LangPackageTableCnData = load_table(
            table_dir, "LangPackageTableCnData", LangPb.LangPackageTableCnData
        )
        for unit in lang_data.Units:
            self.LangMap[unit.id] = unit.content

        # Step 2: 道具表 -> ItemMap
        item_data: ItemPb.ItemData = load_table(
            table_dir, "ItemData", ItemPb.ItemData
        )
        for item in item_data.Units:
            self.ItemMap[item.id] = item

        # Step 3: 卡池表 -> ItemRankMap + UpItemMap
        gacha_data: GachaPb.GachaData = load_table(
            table_dir, "GachaData", GachaPb.GachaData
        )
        for unit in gacha_data.Units:
            pool_id = unit.id
            self.ItemRankMap[pool_id] = {}

            # 3A: RateDesGun (人形星级分布串)
            rate_des_gun = (unit.rateDesGun or "").replace("：", ":")
            for group in rate_des_gun.split(","):
                group = group.strip()
                rank, id_str = _parse_rate_group(group)
                if rank is not None and id_str:
                    for sid in id_str.split(":"):
                        try:
                            self.ItemRankMap[pool_id][int(sid.strip())] = rank
                        except ValueError:
                            pass

            # 3B: RateDesWeapon (武器星级分布串)
            rate_des_weapon = (unit.rateDesWeapon or "").replace("：", ":")
            for group in rate_des_weapon.split(","):
                group = group.strip()
                rank, id_str = _parse_rate_group(group)
                if rank is not None and id_str:
                    for sid in id_str.split(":"):
                        try:
                            self.ItemRankMap[pool_id][int(sid.strip())] = rank
                        except ValueError:
                            pass

            # 3C: UP 物品 (仅限定池 type==3 或 type==4)
            if unit.type == 3 or unit.type == 4:
                up_str = unit.gunUpItem or unit.weaponUpItem or ""
                for up_group in up_str.split(","):
                    up_group = up_group.strip()
                    if up_group.startswith("5:"):
                        try:
                            self.UpItemMap[pool_id] = int(up_group[2:].strip())
                        except ValueError:
                            pass
                        break


def _parse_rate_group(group: str):
    """解析单个星级组字符串，返回 (rank, id_list_string) 或 (None, '')"""
    for prefix in ("5:", "4:", "3:"):
        if group.startswith(prefix):
            return int(prefix[0]), group[2:]
    return None, ""


# ============================================================
# 提取 SSR 表（最终输出格式与 ssr.json 一致）
# ============================================================

# 常驻池基础列表（与原 ssr.json 保持一致）
PERMANENT_BASE_IDS = {
    "1015", "1021", "1025", "1027", "1029", "1033", "1043", "1049",
    "10333", "11016", "11020", "11038", "11044", "11047",
}
"""原 ssr.json 中 SSR_permanent 的 14 个条目 ID"""

PERMANENT_EXTRA = {
    "10433": "赫斯提亚",
    "10493": "二律背反",
}
"""常驻池额外补充项（在原 14 条基础上新增）"""


def extract_ssr_tables(taber: SSRTabler) -> dict:
    """
    从映射表中提取标准格式的 SSR 表
    返回: {
        "version": "local-proto",
        "SSR_character": {"id": "名称", ...},   # 所有限定/UP池5星人形
        "SSR_weapon":    {"id": "名称", ...},   # 所有限定/UP池5星武器
        "SSR_permanent": {"id": "名称", ...},   # 原ssr.json的14条 + 补充2条
    }
    """
    ssr_character: Dict[str, str] = {}
    ssr_weapon: Dict[str, str] = {}
    ssr_permanent: Dict[str, str] = {}

    seen_character = set()
    seen_weapon = set()

    for pool_id, rank_map in taber.ItemRankMap.items():
        is_limited = pool_id in taber.UpItemMap
        for item_id, rank in rank_map.items():
            if rank != 5:
                continue

            item = taber.ItemMap.get(item_id)
            if item is None:
                continue

            name = taber.LangMap.get(item.name.id, f"(unknown:{item.name.id})")
            sid = str(item_id)

            if item.type == 10:  # 人形
                if item_id not in seen_character:
                    seen_character.add(item_id)
                    if is_limited:
                        ssr_character[sid] = name
                # 常驻池：仅包含预定义的 ID（原 ssr.json 的 14 条）
                if sid in PERMANENT_BASE_IDS:
                    ssr_permanent[sid] = name
            elif item.type == 20:  # 武器
                if item_id not in seen_weapon:
                    seen_weapon.add(item_id)
                    if is_limited:
                        ssr_weapon[sid] = name
                # 常驻池：仅包含预定义的 ID（原 ssr.json 的 14 条）
                if sid in PERMANENT_BASE_IDS:
                    ssr_permanent[sid] = name

    # 补充常驻池额外项（赫斯提亚、二律背反）
    for eid, ename in PERMANENT_EXTRA.items():
        if eid not in ssr_permanent:
            # 额外补充项尝试从 protobuf 取名，没有则用默认名
            try:
                iid = int(eid)
                item_obj = taber.ItemMap.get(iid)
                if item_obj:
                    found_name = taber.LangMap.get(item_obj.name.id)
                    if found_name:
                        ssr_permanent[eid] = found_name
                        continue
            except (ValueError, TypeError):
                pass
            ssr_permanent[eid] = ename

    return {
        "version": "local-proto",
        "SSR_character": ssr_character,
        "SSR_weapon": ssr_weapon,
        "SSR_permanent": ssr_permanent,
    }


# ============================================================
# 公开入口函数 - 供 main.py 调用
# ============================================================

# 缓存，避免重复解析（解析需要读大文件，耗时约1-2秒）
_cached_result: Optional[dict] = None


def load_ssr_from_local() -> dict:
    """
    从本地游戏数据解析 SSR 表（带缓存）
    成功时返回标准 SSR 表字典
    失败时返回 None
    """
    global _cached_result
    if _cached_result is not None:
        return _cached_result

    print("[SSR-Proto] 开始从本地游戏数据解析 SSR 表...")

    try:
        table_dir = get_table_dir()
        if table_dir is None:
            print("[SSR-Proto] 无法找到游戏数据目录(Player.log)")
            return None

        if not Path(table_dir).exists():
            print(f"[SSR-Proto] Table 目录不存在: {table_dir}")
            return None

        print(f"[SSR-Proto] Table 目录: {table_dir}")

        taber = SSRTabler()
        taber.load_all(table_dir)

        result = extract_ssr_tables(taber)

        char_count = len(result["SSR_character"])
        weapon_count = len(result["SSR_weapon"])
        perm_count = len(result["SSR_permanent"])

        print(
            f"[SSR-Proto] ★★★ 本地解析成功！ "
            f"人形={char_count}, 武器={weapon_count}, 常驻={perm_count} ★★★"
        )

        # 保存到 JSON 文件方便查看
        _output_path = Path(__file__).parent / "ssr_parsed.json"
        with open(_output_path, "w", encoding="utf-8") as _f:
            json.dump(result, _f, ensure_ascii=False, indent=2)
        print(f"[SSR-Proto] 已保存到: {_output_path}")

        _cached_result = result
        return result

    except Exception as e:
        print(f"[SSR-Proto] 解析失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def clear_cache():
    """清除缓存，强制下次重新解析"""
    global _cached_result
    _cached_result = None
