import json
from pathlib import Path
import asyncio
import copy
import aiohttp


def set_gacha_Banner(id, json_path=None):
    """设置抽卡池类型（文件版本，保留兼容性）

    Args:
        id: 池子类型ID (1=常驻池, 3=角色池, 4=武器池, 6=自选角色池, 7=自选武器池)
        json_path: json文件路径，默认使用 latest_request.json
    """
    if json_path is None:
        json_path = Path(__file__).parent.parent.parent / "json" / "latest_request.json"

    try:
        if not json_path.exists():
            print("[ERROR] 请求数据不存在")
            return False
        with open(json_path, "r", encoding="utf-8") as f:
            latest_request = json.load(f)
    except Exception as e:
        print(f"[ERROR] 读取请求数据失败: {e}")
        return False

    latest_request["body"]["type_id"] = id

    if "next" in latest_request["body"]:
        del latest_request["body"]["next"]

    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(latest_request, f, ensure_ascii=False, indent=4)
            print(f"[OK] 保存请求数据成功: {json_path}")
        return True
    except Exception as e:
        print(f"[ERROR] 保存请求数据失败: {e}")
        return False


def _set_gacha_banner_dict(request_data, pool_type_id):
    """设置抽卡池类型（内存版本）

    Args:
        request_data: 请求数据字典
        pool_type_id: 池子类型ID

    Returns:
        修改后的请求数据字典
    """
    request_data["body"]["type_id"] = pool_type_id
    if "next" in request_data["body"]:
        del request_data["body"]["next"]
    return request_data


async def _get_gacha_data_one_async(request_data, session):
    """获取单页抽卡数据（真异步版本，使用 aiohttp）

    Args:
        request_data: 请求数据字典，会被原地修改
        session: aiohttp ClientSession

    Returns:
        响应JSON数据，失败返回 None
    """
    BASE_URL = "https://gf2-gacha-record.sunborngame.com/list"
    params = request_data["params"]
    data = request_data["body"]
    headers = dict(request_data["headers"])

    if "next" in request_data["body"]:
        ContentLength = len("next=" + request_data["body"]["next"] + "&" + "type_id=" + request_data["body"]["type_id"])
    else:
        ContentLength = len("type_id=" + request_data["body"]["type_id"])
    headers["Content-Length"] = str(ContentLength)

    try:
        async with session.post(
            url=BASE_URL,
            params=params,
            data=data,
            headers=headers,
            ssl=False,
            allow_redirects=False
        ) as response:
            response_json = await response.json()
            next_value = response_json["data"]["next"]

            if next_value != "":
                request_data["body"]["next"] = next_value
            else:
                if "next" in request_data["body"]:
                    del request_data["body"]["next"]

            return response_json

    except Exception as e:
        print(f"[ERROR] 请求失败：{str(e)}")
        return None


async def get_gacha_pool_async(pool_type_id, pool_name, session):
    """异步获取单个池子的所有数据（真异步版本）

    Args:
        pool_type_id: 池子类型ID (1=常驻池, 3=角色池, 4=武器池, 6=自选角色池, 7=自选武器池)
        pool_name: 池子名称（用于日志）
        session: aiohttp ClientSession（共享session提升性能）

    Returns:
        池子的完整数据列表，如果获取失败返回 None
    """
    original_json_path = Path(__file__).parent.parent.parent / "json" / "latest_request.json"

    try:
        if not original_json_path.exists():
            print(f"[ERROR] 请求数据不存在: {original_json_path}")
            return None
        with open(original_json_path, "r", encoding="utf-8") as f:
            base_request = json.load(f)
    except Exception as e:
        print(f"[ERROR] 读取请求数据失败: {e}")
        return None

    request_data = copy.deepcopy(base_request)
    _set_gacha_banner_dict(request_data, pool_type_id)

    response = await _get_gacha_data_one_async(request_data, session)
    if response is None:
        print(f"[ERROR] 获取{pool_name}第一页数据失败")
        return None

    gacha_data = [response]
    print(f"[OK] 获取{pool_name}第一页数据成功")

    page = 2
    while response["data"]["next"] != "":
        response = await _get_gacha_data_one_async(request_data, session)
        if response is None:
            print(f"[ERROR] 获取{pool_name}第{page}页数据失败")
            return None
        gacha_data.append(response)
        print(f"[OK] 获取{pool_name}第{page}页数据成功")
        page += 1

    print(f"[OK] {pool_name}数据获取完成，共{len(gacha_data)}页")
    return gacha_data


async def _get_all_pools_async():
    """并行获取所有池子数据的内部异步函数"""
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            get_gacha_pool_async("1", "常驻池", session),
            get_gacha_pool_async("3", "角色池", session),
            get_gacha_pool_async("4", "武器池", session),
            get_gacha_pool_async("6", "自选角色池", session),
            get_gacha_pool_async("7", "自选武器池", session)
        )
        return results


def get_gacha_data_all():
    """并行获取所有池子的抽卡数据"""
    print("[INFO] 开始并行获取五个池子的数据...")

    try:
        results = asyncio.run(_get_all_pools_async())

        gacha_data_Permanent, gacha_data_Character, gacha_data_Weapon, gacha_data_CustomCharacter, gacha_data_CustomWeapon = results

        if (gacha_data_Permanent is None or gacha_data_Character is None or
            gacha_data_Weapon is None or gacha_data_CustomCharacter is None or
            gacha_data_CustomWeapon is None):
            print("[ERROR] 部分池子数据获取失败")
            return None

        print("[OK] 所有池子数据获取完成")

        return {
            "permanent_pool": gacha_data_Permanent,
            "character_pool": gacha_data_Character,
            "weapon_pool": gacha_data_Weapon,
            "custom_character_pool": gacha_data_CustomCharacter,
            "custom_weapon_pool": gacha_data_CustomWeapon
        }
    except Exception as e:
        print(f"[ERROR] 获取抽卡数据失败: {e}")
        return None


if __name__ == "__main__":
    get_gacha_data_all()
