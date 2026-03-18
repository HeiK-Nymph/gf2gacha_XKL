import requests
import json
from pathlib import Path
import asyncio
import shutil
import tempfile


def set_gacha_Banner(id, json_path=None):
    """设置抽卡池类型

    Args:
        id: 池子类型ID (1=常驻池, 3=角色池, 4=武器池)
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

    if "next" in latest_request["body"]:  # 先判断键存在再删除，避免报KeyError
        del latest_request["body"]["next"]
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(latest_request, f, ensure_ascii=False, indent=4)
                print(f"[OK] 保存请求数据成功: {json_path}")
            return True
        except Exception as e:
            print(f"[ERROR] 保存请求数据失败: {e}")
            return False
    else:
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(latest_request, f, ensure_ascii=False, indent=4)
                print(f"[OK] 保存请求数据成功: {json_path}")
            return True
        except Exception as e:
            print(f"[ERROR] 保存请求数据失败: {e}")
            return False



def get_gacha_data_one(json_path=None):
    """获取单页抽卡数据

    Args:
        json_path: json文件路径，默认使用 latest_request.json
    """
    if json_path is None:
        json_path = Path(__file__).parent.parent.parent / "json" / "latest_request.json"

    


    try:
        if not json_path.exists():
            print("[ERROR] 请求数据不存在")
            return None
        with open(json_path, "r", encoding="utf-8") as f:
            latest_request = json.load(f)
    except Exception as e:
        print(f"[ERROR] 读取请求数据失败: {e}")
        return None


    BASE_URL = "https://gf2-gacha-record.sunborngame.com/list"
    params = latest_request["params"]
    data = latest_request["body"]
    headers = latest_request["headers"]

    if ("next" in latest_request["body"]):
        ContentLength = len("next=" + latest_request["body"]["next"] + "&" + "type_id=" + latest_request["body"]["type_id"])
    else:
        ContentLength = len("type_id=" + latest_request["body"]["type_id"])
    headers["Content-Length"] = str(ContentLength)

    try:
        # params=params：自动拼接成URL查询参数；data=data：自动转成表单格式
        response = requests.post(
            url=BASE_URL,
            params=params,
            data=data,
            headers=headers,
            verify=False,
            # 可选：开启gzip解压（匹配Accept-Encoding），requests会自动处理
            allow_redirects=False
        )
        # 打印请求结果：状态码 + 响应内容
        # print(f"[OK] 请求成功，状态码：{response.status_code}")
        # print(f"[INFO] 响应内容：{response.text}")

        next_value = response.json()["data"]["next"]
        

        if next_value != "":
            latest_request["body"]["next"] = next_value

            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(latest_request, f, ensure_ascii=False, indent=4)
                    print(f"[OK] 保存请求数据成功: {json_path}")

                return response.json()
                    
            except Exception as e:
                print(f"[ERROR] 保存请求数据失败: {e}")
                return None

            

        else:
            if "next" in latest_request["body"]:  # 先判断键存在再删除，避免报KeyError
                del latest_request["body"]["next"]
            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(latest_request, f, ensure_ascii=False, indent=4)
                    print(f"[OK] 保存请求数据成功: {json_path}")

                return response.json()
                    
            except Exception as e:
                print(f"[ERROR] 保存请求数据失败: {e}")
                return None
            
    except Exception as e:
        print(f"[ERROR] 请求失败：{str(e)}")
        return None


async def get_gacha_data_one_async(json_path):
    """异步获取单页抽卡数据

    Args:
        json_path: json文件路径
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_gacha_data_one, json_path)


async def get_gacha_pool_async(pool_type_id, pool_name):
    """异步获取单个池子的所有数据

    Args:
        pool_type_id: 池子类型ID (1=常驻池, 3=角色池, 4=武器池)
        pool_name: 池子名称（用于日志）

    Returns:
        池子的完整数据列表，如果获取失败返回 None
    """
    # 创建临时文件用于该池子的状态管理
    original_json_path = Path(__file__).parent.parent.parent / "json" / "latest_request.json"
    temp_json_path = Path(tempfile.gettempdir()) / f"gf2_gacha_{pool_name}_{pool_type_id}.json"

    try:
        # 复制原始配置到临时文件
        shutil.copy(original_json_path, temp_json_path)
        print(f"[INFO] 创建临时配置文件: {temp_json_path}")

        # 设置池子类型
        set_gacha_Banner(pool_type_id, temp_json_path)

        # 异步获取第一页
        response = await get_gacha_data_one_async(temp_json_path)
        if response is None:
            print(f"[ERROR] 获取{pool_name}第一页数据失败")
            return None  # 返回 None 表示获取失败

        gacha_data = [response]
        print(f"[OK] 获取{pool_name}第一页数据成功")

        # 异步获取剩余页（由于分页有依赖关系，必须串行获取，但使用线程池执行网络请求）
        page = 2
        while response["data"]["next"] != "":
            response = await get_gacha_data_one_async(temp_json_path)
            if response is None:
                print(f"[ERROR] 获取{pool_name}第{page}页数据失败")
                return None  # 返回 None 表示获取失败
            gacha_data.append(response)
            print(f"[OK] 获取{pool_name}第{page}页数据成功")
            page += 1

        print(f"[OK] {pool_name}数据获取完成，共{len(gacha_data)}页")
        return gacha_data

    except Exception as e:
        print(f"[ERROR] 获取{pool_name}数据失败: {e}")
        return None  # 返回 None 表示获取失败
    finally:
        # 清理临时文件
        if temp_json_path.exists():
            temp_json_path.unlink()
            print(f"[INFO] 删除临时配置文件: {temp_json_path}")


def get_gacha_data_all():
    """并行获取所有池子的抽卡数据"""
    print("[INFO] 开始并行获取三个池子的数据...")

    # 使用 asyncio 并行获取三个池子的数据
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # 并行执行三个池子的数据获取
        results = loop.run_until_complete(asyncio.gather(
            get_gacha_pool_async("1", "常驻池"),
            get_gacha_pool_async("3", "角色池"),
            get_gacha_pool_async("4", "武器池")
        ))

        gacha_data_Permanent, gacha_data_Character, gacha_data_Weapon = results

        # 检查是否有任何一个池子获取失败（返回 None）
        if gacha_data_Permanent is None or gacha_data_Character is None or gacha_data_Weapon is None:
            print("[ERROR] 部分池子数据获取失败")
            return None  # 返回 None 表示获取失败

        print("[OK] 所有池子数据获取完成")

        return {
            "permanent_pool": gacha_data_Permanent,  # 常驻池
            "character_pool": gacha_data_Character,  # 角色池
            "weapon_pool": gacha_data_Weapon         # 武器池
        }
    except Exception as e:
        print(f"[ERROR] 获取抽卡数据失败: {e}")
        return None  # 返回 None 表示获取失败
    finally:
        loop.close()
    

    

if __name__ == "__main__":
    get_gacha_data_all()