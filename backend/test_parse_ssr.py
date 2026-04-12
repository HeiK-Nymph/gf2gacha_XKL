"""
从游戏本地数据（.bytes 文件）解析 SSR 表的完整流程
参考 Matcha 项目: D:\myproject\gf2gacha_Matcha\matcha\gf2gacha

完整流程：
1. 从 Player.log 读取游戏安装路径 -> 拼接出 Table 目录
2. 解析 .bytes 文件（前4字节为头部偏移，后面是 protobuf 数据）
3. 构建 LangMap、ItemMap，再从 GachaData 提取各卡池的5星物品
4. 输出完整的 SSR 表：SSR_character(5星人形), SSR_weapon(5星武器), SSR_permanent(常驻池5星)

用法: python test_parse_ssr.py [player_log_path]
      不传参数则自动查找 Player.log
"""

import os
import sys
import re
import struct
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================
# Step 0: 安装依赖（首次运行）
# ============================================================
def ensure_dependencies():
    """检查并提示安装 protobuf 库"""
    try:
        import google.protobuf
        print(f"[OK] protobuf 已安装, 版本: {google.protobuf.__version__}")
    except ImportError:
        print("[INFO] 需要安装 protobuf 库...")
        os.system('pip install protobuf')
        print("[OK] 安装完成")


def compile_proto():
    """编译 .proto 文件为 Python 模块"""
    from grpc_tools import protoc

    proto_dir = Path(__file__).parent / "proto"
    output_dir = proto_dir.parent / "pb"

    # 确保 proto 目录存在
    if not proto_dir.exists():
        print(f"[ERROR] proto 目录不存在: {proto_dir}")
        return False

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 编译所有 .proto 文件
    proto_files = list(proto_dir.glob("*.proto"))
    if not proto_files:
        print(f"[ERROR] 未找到 .proto 文件在 {proto_dir}")
        return False

    print(f"[INFO] 找到 {len(proto_files)} 个 proto 文件，开始编译...")

    import sys as _sys
    args = [
        "grpc_tools.protoc",
        f"--python_out={output_dir}",
        f"--proto_path={proto_dir}",
    ] + [str(p) for p in proto_files]

    ret = protoc.main(args)

    if ret == 0:
        print(f"[OK] Proto 编译成功，输出到: {output_dir}")

        # 创建 __init__.py 使其成为包
        init_file = output_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("# auto-generated\n")

        return True
    else:
        print("[ERROR] Proto 编译失败！")
        return False


# ============================================================
# Step 1: 从 Player.log 获取游戏 Table 目录路径
# ============================================================
def find_player_log(custom_path: str = None) -> Optional[Path]:
    """
    查找 Player.log 文件
    路径: %USERPROFILE%/AppData/LocalLow/SunBorn/少女前线2：追放/Player.log
    或   : %USERPROFILE%/AppData/LocalLow/SunBorn/Girls' Frontline 2/Player.log
    """
    if custom_path:
        path = Path(custom_path)
        if path.exists():
            return path
        print(f"[WARNING] 指定的日志文件不存在: {custom_path}")
        return None

    user_profile = Path(os.environ.get("USERPROFILE", ""))
    possible_paths = [
        user_profile / "AppData" / "LocalLow" / "SunBorn" / "少女前线2：追放" / "Player.log",
        user_profile / "AppData" / "LocalLow" / "SunBorn" / "Girls' Frontline 2" / "Player.log",
        user_profile / "AppData" / "LocalLow" / "SunBorn" / "Girls Frontline 2" / "Player.log",
    ]

    for log_path in possible_paths:
        if log_path.exists():
            return log_path

    print("[ERROR] 未找到 Player.log，请手动指定路径:")
    for p in possible_paths:
        print(f"       {p}")
    return None


def get_game_data_dir_from_log(player_log: Path) -> Optional[str]:
    """
    从 Player.log 提取游戏安装根目录
    正则: [Subsystems] Discovering subsystems at path (.+)/UnitySubsystems
    返回: {gameRoot}/LocalCache/Data
    """
    content = player_log.read_text(encoding="utf-8", errors="ignore")

    match = re.search(
        r'\[Subsystems\] Discovering subsystems at path (.+)/UnitySubsystems',
        content
    )

    if not match:
        print("[ERROR] 无法从 Player.log 中找到游戏路径")
        print("       请确认游戏至少运行过一次")
        return None

    game_root = match.group(1).strip()
    game_data_dir = os.path.join(game_root, "LocalCache", "Data")
    print(f"[INFO] 游戏根目录: {game_root}")
    print(f"[INFO] 游戏数据目录: {game_data_dir}")
    return game_data_dir


# ============================================================
# Step 2: 解析 .bytes 文件（带头部）
# ============================================================
def parse_bytes_file(file_path: Path, message_class) -> object:
    """
    解析游戏的 .bytes 配置表文件
    文件格式:
      偏移 0~3:     uint32 Little-Endian 头部偏移值
      偏移 head+4~末尾: Protobuf 序列化数据
    """
    if not file_path.exists():
        raise FileNotFoundError(f"bytes 文件不存在: {file_path}")

    raw = file_path.read_bytes()
    if len(raw) < 4:
        raise ValueError(f"文件太小: {file_path} ({len(raw)} bytes)")

    head = struct.unpack('<I', raw[:4])[0]
    print(f"[DEBUG] 解析 {file_path.name}: head={head}, 总大小={len(raw)}, proto数据大小={len(raw)-head-4}")

    if head + 4 > len(raw):
        raise ValueError(f"头偏移值异常: head={head}, 文件大小={len(raw)}")

    proto_data = raw[head + 4:]
    msg = message_class()
    msg.ParseFromString(proto_data)
    return msg


def load_table(table_dir: str, table_name: str, message_class) -> object:
    """加载指定名称的表"""
    file_path = Path(table_dir) / f"{table_name}.bytes"
    return parse_bytes_file(file_path, message_class)


# ============================================================
# Step 3: 构建所有映射表（完全复刻 preload/init.go 的逻辑）
# ============================================================
class SSRTabler:
    """
    完整复刻 Matcha 项目 preload/init.go 的逻辑
    
    全局变量映射:
      LangMap     -> 语言ID -> 中文名
      ItemMap     -> 道具ID -> ItemDataUnit
      UpItemMap   -> 卡池ID -> UP道具的5星ID
      ItemRankMap -> 卡池ID -> {道具ID -> 在该池中的星级(3/4/5)}
      PoolTypeMap -> 卡池类型ID -> GachaTypeListDataUnit
      DollNameMapping   -> 中文名 -> 道具ID (人形 type=10)
      WeaponNameMapping -> 中文名 -> 道具ID (武器 type=20)
    """

    def __init__(self):
        self.LangMap: Dict[int, str] = {}
        self.ItemMap: Dict[int, object] = {}  # ItemDataUnit
        self.UpItemMap: Dict[int, int] = {}  # poolId -> upItemId
        self.ItemRankMap: Dict[int, Dict[int, int]] = {}  # poolId -> {itemId -> rank}
        self.PoolTypeMap: Dict[int, object] = {}  # GachaTypeListDataUnit
        self.DollNameMapping: Dict[str, int] = {}
        self.WeaponNameMapping: Dict[str, int] = {}

    def load_all(self, table_dir: str):
        """加载所有配置表并构建映射"""
        # 确保能找到生成的 _pb2 模块
        import LangPackageTableCnData_pb2 as LangPb
        import ItemData_pb2 as ItemPb
        import GachaData_pb2 as GachaPb
        import GachaTypeListData_pb2 as TypePb

        # ---- Step 1: 加载语言包 -> LangMap ----
        print("\n[Step 1] 加载 LangPackageTableCnData.bytes ...")
        lang_data: LangPb.LangPackageTableCnData = load_table(
            table_dir, "LangPackageTableCnData", LangPb.LangPackageTableCnData
        )
        for unit in lang_data.Units:
            self.LangMap[unit.id] = unit.content
        print(f"  -> LangMap: {len(self.LangMap)} 条")

        # ---- Step 2: 加载道具表 -> ItemMap + NameMapping ----
        print("\n[Step 2] 加载 ItemData.bytes ...")
        item_data: ItemPb.ItemData = load_table(
            table_dir, "ItemData", ItemPb.ItemData
        )
        for item in item_data.Units:
            self.ItemMap[item.id] = item
            if item.type == 10:  # 人形/Doll
                name_str = self.LangMap.get(item.name.id, "")
                if name_str:
                    self.DollNameMapping[name_str] = item.id
            elif item.type == 20:  # 武器/Weapon
                name_str = self.LangMap.get(item.name.id, "")
                if name_str:
                    self.WeaponNameMapping[name_str] = item.id
        print(f"  -> ItemMap: {len(self.ItemMap)} 条")
        print(f"  -> DollNameMapping: {len(self.DollNameMapping)} 条")
        print(f"  -> WeaponNameMapping: {len(self.WeaponNameMapping)} 条")

        # ---- Step 3: 加载卡池表 -> ItemRankMap + UpItemMap (核心!) ----
        print("\n[Step 3] 加载 GachaData.bytes ...")
        gacha_data: GachaPb.GachaData = load_table(
            table_dir, "GachaData", GachaPb.GachaData
        )
        for unit in gacha_data.Units:
            pool_id = unit.id
            self.ItemRankMap[pool_id] = {}

            # 3A. 解析 RateDesGun (人形星级分布串)
            # 格式: "5:id1:id2,4:id3,3:id4"  (散爆混用中英文冒号)
            rate_des_gun = unit.rateDesGun.replace("：", ":") if unit.rateDesGun else ""
            if rate_des_gun:
                for group in rate_des_gun.split(","):
                    group = group.strip()
                    if not group:
                        continue
                    rank = None
                    id_list_str = ""
                    if group.startswith("5:"):
                        rank = 5
                        id_list_str = group[2:]
                    elif group.startswith("4:"):
                        rank = 4
                        id_list_str = group[2:]
                    elif group.startswith("3:"):
                        rank = 3
                        id_list_str = group[2:]

                    if rank is not None and id_list_str:
                        for doll_id_str in id_list_str.split(":"):
                            try:
                                doll_id = int(doll_id_str.strip())
                                self.ItemRankMap[pool_id][doll_id] = rank
                            except ValueError:
                                pass

            # 3B. 解析 RateDesWeapon (武器星级分布串)
            rate_des_weapon = unit.rateDesWeapon.replace("：", ":") if unit.rateDesWeapon else ""
            if rate_des_weapon:
                for group in rate_des_weapon.split(","):
                    group = group.strip()
                    if not group:
                        continue
                    rank = None
                    id_list_str = ""
                    if group.startswith("5:"):
                        rank = 5
                        id_list_str = group[2:]
                    elif group.startswith("4:"):
                        rank = 4
                        id_list_str = group[2:]
                    elif group.startswith("3:"):
                        rank = 3
                        id_list_str = group[2:]

                    if rank is not None and id_list_str:
                        for weapon_id_str in id_list_str.split(":"):
                            try:
                                weapon_id = int(weapon_id_str.strip())
                                self.ItemRankMap[pool_id][weapon_id] = rank
                            except ValueError:
                                pass

            # 3C. 提取 UP 物品 (仅限定池 type==3 或 type==4)
            if unit.type == 3 or unit.type == 4:
                up_item_group_string = unit.gunUpItem or unit.weaponUpItem or ""
                if up_item_group_string:
                    for up_group in up_item_group_string.split(","):
                        up_group = up_group.strip()
                        if up_group.startswith("5:"):
                            up_item_str = up_group[2:].strip()
                            try:
                                up_item_id = int(up_item_str)
                                self.UpItemMap[pool_id] = up_item_id
                                break
                            except ValueError:
                                pass

        print(f"  -> ItemRankMap: {len(self.ItemRankMap)} 个卡池")
        print(f"  -> UpItemMap: {len(self.UpItemMap)} 个限定池UP信息")

        # ---- Step 4: 加载卡池类型列表 -> PoolTypeMap ----
        print("\n[Step 4] 加载 GachaTypeListData.bytes ...")
        type_data: TypePb.GachaTypeListData = load_table(
            table_dir, "GachaTypeListData", TypePb.GachaTypeListData
        )
        for unit in type_data.Units:
            self.PoolTypeMap[unit.id] = unit
        print(f"  -> PoolTypeMap: {len(self.PoolTypeMap)} 种类型")

        # 打印卡池类型
        for tid, tunit in sorted(self.PoolTypeMap.items()):
            print(f"     类型 {tunit.id}: {tunit.name}")


# ============================================================
# Step 4: 提取 SSR 表（最终输出）
# ============================================================
def extract_ssr_tables(taber: SSRTabler) -> dict:
    """
    从构建好的映射表中提取 SSR 表
    参考 ssr.json 的结构:
      SSR_character:  {id: 名称}   - 所有限定/UP池的5星人形
      SSR_weapon:     {id: 名称}   - 所有限定/UP池的5星武器
      SSR_permanent:  {id: 名称}   - 常驻池(type=1)的5星物品
    """
    ssr_character = {}  # id -> name
    ssr_weapon = {}     # id -> name
    ssr_permanent = {}  # id -> name

    # 收集所有5星物品及其所属的卡池类型
    all_rank5_items = []  # [(item_id, item_name, pool_type, pool_id)]

    for pool_id, rank_map in taber.ItemRankMap.items():
        # 确定这个卡池的类型（需要从 GachaData 反查）
        # 但我们这里简化处理：遍历所有卡池的5星物品
        for item_id, rank in rank_map.items():
            if rank != 5:
                continue

            # 获取物品信息
            item = taber.ItemMap.get(item_id)
            if item is None:
                continue

            # 获取名称
            name = taber.LangMap.get(item.name.id, f"(unknown:{item.name.id})")

            is_limited_pool = pool_id in taber.UpItemMap  # 有UP信息的视为限定池
            all_rank5_items.append((item_id, name, item.type, is_limited_pool))

    # 去重后分类
    seen_character = set()  # 用于去重的集合
    seen_weapon = set()

    for item_id, name, item_type, is_limited in all_rank5_items:
        if item_type == 10:  # 人形
            if item_id not in seen_character:
                seen_character.add(item_id)
                if is_limited:
                    ssr_character[str(item_id)] = name
                ssr_permanent[str(item_id)] = name
        elif item_type == 20:  # 武器
            if item_id not in seen_weapon:
                seen_weapon.add(item_id)
                if is_limited:
                    ssr_weapon[str(item_id)] = name
                ssr_permanent[str(item_id)] = name

    return {
        "SSR_character": ssr_character,
        "SSR_weapon": ssr_weapon,
        "SSR_permanent": ssr_permanent,
        "_raw_stats": {
            "total_lang_entries": len(taber.LangMap),
            "total_items": len(taber.ItemMap),
            "total_dolls": len(taber.DollNameMapping),
            "total_weapons": len(taber.WeaponNameMapping),
            "total_pools": len(taber.ItemRankMap),
            "limited_pools": len(taber.UpItemMap),
            "rank5_character_in_limited": len(ssr_character),
            "rank5_weapon_in_limited": len(ssr_weapon),
            "rank5_in_permanent": len(ssr_permanent),
        }
    }


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("  GF2Gacha SSR 表解析器 (Python版)")
    print("  参考 Matcha 项目 protobuf 解析方案")
    print("=" * 60)

    # 0. 确保依赖
    ensure_dependencies()

    # 1. 编译 proto
    script_dir = Path(__file__).parent
    pb_dir = script_dir / "pb"

    # 检查是否已有编译结果
    has_pb = pb_dir.exists() and any(pb_dir.glob("*_pb2.py"))
    if not has_pb:
        if not compile_proto():
            print("\n[ERROR] Proto 编译失败，退出")
            sys.exit(1)
    else:
        print(f"\n[INFO] 使用已有的 pb 模块: {pb_dir}")

    # 将 pb 目录加入搜索路径（生成的 _pb2 文件之间有相互引用，需要直接 import）
    pb_path = str(pb_dir)
    if pb_path not in sys.path:
        sys.path.insert(0, pb_path)
    backend_path = str(script_dir.parent)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    # 2. 查找 Player.log
    custom_log = sys.argv[1] if len(sys.argv) > 1 else None
    player_log = find_player_log(custom_log)
    if player_log is None:
        print("\n[ERROR] 无法定位 Player.log")
        print("       用法: python test_parse_ssr.py [player_log_路径]")
        sys.exit(1)

    print(f"\n[INFO] Player.log 路径: {player_log}")

    # 3. 获取 Table 目录
    game_data_dir = get_game_data_dir_from_log(player_log)
    if game_data_dir is None:
        sys.exit(1)

    table_dir = os.path.join(game_data_dir, "Table")
    if not Path(table_dir).exists():
        print(f"[ERROR] Table 目录不存在: {table_dir}")
        sys.exit(1)

    print(f"\n[INFO] Table 目录: {table_dir}")

    # 列出可用的 .bytes 文件
    bytes_files = sorted(Path(table_dir).glob("*.bytes"))
    print(f"\n[INFO] 找到 {len(bytes_files)} 个 .bytes 文件:")
    for bf in bytes_files[:20]:  # 只显示前20个
        size_kb = bf.stat().st_size / 1024
        print(f"       {bf.name} ({size_kb:.1f} KB)")
    if len(bytes_files) > 20:
        print(f"       ... 还有 {len(bytes_files) - 20} 个")

    # 4. 构建映射表
    print("\n" + "=" * 60)
    print("  开始加载数据表...")
    print("=" * 60)

    taber = SSRTabler()
    taber.load_all(table_dir)

    # 5. 提取并打印 SSR 表
    print("\n" + "=" * 60)
    print("  SSR 表解析结果")
    print("=" * 60)

    result = extract_ssr_tables(taber)
    stats = result.pop("_raw_stats")

    # 格式化输出
    print(f"\n{'='*50}")
    print(f"  SSR_character (限定/UP池 5星人形): {len(result['SSR_character'])} 个")
    print(f"{'='*50}")
    for item_id, name in sorted(result["SSR_character"].items(), key=lambda x: x[0]):
        print(f"    {item_id:>6s}  →  {name}")

    print(f"\n{'='*50}")
    print(f"  SSR_weapon (限定/UP池 5星武器): {len(result['SSR_weapon'])} 个")
    print(f"{'='*50}")
    for item_id, name in sorted(result["SSR_weapon"].items(), key=lambda x: x[0]):
        print(f"    {item_id:>6s}  →  {name}")

    print(f"\n{'='*50}")
    print(f"  SSR_permanent (常驻池5星): {len(result['SSR_permanent'])} 个")
    print(f"{'='*50}")
    for item_id, name in sorted(result["SSR_permanent"].items(), key=lambda x: x[0]):
        print(f"    {item_id:>6s}  →  {name}")

    # 统计信息
    print(f"\n{'='*50}")
    print("  统计信息")
    print(f"{'='*50}")
    for k, v in stats.items():
        print(f"    {k}: {v}")

    # 输出 JSON 格式（方便对比）
    json_output = {
        "version": "auto-generated",
        "SSR_character": result["SSR_character"],
        "SSR_weapon": result["SSR_weapon"],
        "SSR_permanent": result["SSR_permanent"],
    }

    output_json = Path(__file__).parent / "ssr_parsed.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] JSON 已保存到: {output_json}")


if __name__ == "__main__":
    main()
