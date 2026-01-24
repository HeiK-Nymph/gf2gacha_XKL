import requests
import json
from pathlib import Path


def set_gacha_Banner(id):
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



def get_gacha_data_one():
    

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

def get_gacha_data_all():

    gacha_data_Permanent = []
    gacha_data_Character = []
    gacha_data_Weapon = []


    set_gacha_Banner("1")
    response = get_gacha_data_one()
    gacha_data_Permanent.append(response)
    while response["data"]["next"] != "":
        response = get_gacha_data_one()
        gacha_data_Permanent.append(response)

    set_gacha_Banner("3")
    response = get_gacha_data_one()
    gacha_data_Character.append(response)
    while response["data"]["next"] != "":
        response = get_gacha_data_one()
        gacha_data_Character.append(response)

    set_gacha_Banner("4")
    response = get_gacha_data_one()
    gacha_data_Weapon.append(response)
    while response["data"]["next"] != "":
        response = get_gacha_data_one()
        gacha_data_Weapon.append(response)

    

    return {
        "permanent_pool": gacha_data_Permanent,  # 常驻池
        "character_pool": gacha_data_Character,  # 角色池
        "weapon_pool": gacha_data_Weapon         # 武器池
    }
    

    

if __name__ == "__main__":
    get_gacha_data_all()