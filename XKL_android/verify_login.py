# -*- coding: utf-8 -*-
"""少前2 追放 — 手机号+短信验证码 登录 & 查抽卡记录 端到端验证脚本

运行位置：XKL_android/verify_login.py（运行产物落在同目录 .runtime/ 下）

协议来源见 GF2_SMS_LOGIN_PROTOCOL.md
用法：
    python verify_login.py            # 完整流程：发码 -> 输码 -> 登录 -> 查 5 个池子
    python verify_login.py --token    # 复用上次保存的 token，只查记录
"""
import hashlib
import json
import os
import sys
import time

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.join(BASE, ".runtime")
os.makedirs(RUNTIME, exist_ok=True)
DN_FILE = os.path.join(RUNTIME, "device_num.txt")
TOKEN_FILE = os.path.join(RUNTIME, "token.json")
RESULT_FILE = os.path.join(RUNTIME, "last_result.json")

SMS_URL = "https://gf2-cn-plateuser.sunborngame.com/sms/phone_login"
LOGIN_URL = "https://gf2-zoneinfo.sunborngame.com/phone/sms_login"
LIST_URL = "https://gf2-gacha-record.sunborngame.com/list"

COMMON_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "UnityPlayer/2019.4.40f1 (UnityWebRequest/1.0, libcurl/7.80.0-DEV)",
    "Accept": "*/*",
    "X-Unity-Version": "2019.4.40f1",
}

POOLS = [(1, "常驻池"), (3, "角色池"), (4, "武器池"), (6, "自选角色池"), (7, "自选武器池")]


def get_device_num():
    """稳定的设备号（每台机器固定一个，模拟 PC 客户端的 40 位十六进制）"""
    if os.path.exists(DN_FILE):
        v = open(DN_FILE, encoding="utf-8").read().strip()
        if v:
            return v
    v = os.urandom(20).hex()
    open(DN_FILE, "w", encoding="utf-8").write(v)
    return v


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def make_sign(device_num, phone, ts):
    # 参与签名: device_num / phone_number / timestamp，字典序，& 连接，无密钥
    raw = "device_num=%s&phone_number=%s&timestamp=%s" % (device_num, phone, ts)
    return md5(raw), raw


def common_body(device_num, phone, ts, sign):
    return {
        "os": 3,
        "reyun_channel_id": "1029",
        "game_channel_id": 5,
        "device_num": device_num,
        "timestamp": ts,
        "language": "cn",
        "area_code": "+86",
        "sign": sign,
        "phone_number": phone,
        "mac": "",
    }


def post_json(url, body):
    r = requests.post(url, json=body, headers=COMMON_HEADERS, timeout=20)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"_raw": r.text[:300]}


def send_sms(phone):
    dn = get_device_num()
    ts = int(time.time())
    sign, raw = make_sign(dn, phone, ts)
    body = common_body(dn, phone, ts, sign)
    body["x"] = -1
    print("  [发码] 待签名串 = %s" % raw.replace(phone, phone[:3] + "****" + phone[-4:]))
    st, js = post_json(SMS_URL, body)
    print("  [发码] HTTP %s -> %s" % (st, json.dumps(js, ensure_ascii=False)))
    return js.get("code") == 0


def sms_login(phone, code):
    dn = get_device_num()
    ts = int(time.time())
    sign, raw = make_sign(dn, phone, ts)
    body = common_body(dn, phone, ts, sign)
    body["verify_code"] = code
    st, js = post_json(LOGIN_URL, body)
    print("  [登录] HTTP %s -> code=%s msg=%s" % (st, js.get("code"), js.get("msg")))
    if js.get("code") != 0:
        print("  [登录] 原始返回: %s" % json.dumps(js, ensure_ascii=False)[:400])
        return None
    return js.get("data") or {}


def fetch_pool(token, pool_id):
    hdr = dict(COMMON_HEADERS)
    hdr["Content-Type"] = "application/x-www-form-urlencoded"
    hdr["Authorization"] = token
    params = {"game_channel_id": "5", "type_id": "3"}
    body = {"type_id": str(pool_id)}
    items, page, nxt = [], 1, None
    while True:
        st = requests.post(LIST_URL, params=params, data=body, headers=hdr, timeout=20)
        try:
            js = st.json()
        except Exception:
            return {"ok": False, "err": "HTTP %s 非 JSON: %s" % (st.status_code, st.text[:200])}
        if js.get("code") != 0:
            return {"ok": False, "err": "code=%s message=%s" % (js.get("code"), js.get("message"))}
        data = js.get("data") or {}
        items.extend(data.get("list") or [])
        nxt = data.get("next") or ""
        if not nxt:
            break
        body["next"] = nxt
        page += 1
        if page > 200:
            return {"ok": False, "err": "翻页超过 200 页"}
    return {"ok": True, "pages": page, "count": len(items), "items": items}


def main():
    reuse = "--token" in sys.argv

    if reuse:
        if not os.path.exists(TOKEN_FILE):
            print("没有缓存的 token，请先跑完整流程（不带 --token）")
            return 1
        saved = json.load(open(TOKEN_FILE, encoding="utf-8"))
        token, uid = saved["access_token"], saved.get("uid")
        print("复用缓存 token：uid=%s  token 前缀=%s...（长度 %d）" % (uid, token[:20], len(token)))
    else:
        phone = input("请输入手机号（11 位）：").strip()
        if not (phone.isdigit() and len(phone) == 11):
            print("手机号格式不对")
            return 1
        print("\n=== 第 1 步：请求发送短信验证码 ===")
        if not send_sms(phone):
            print("发码失败，看上面的 code/msg")
            return 1
        code = input("\n请输入收到的 6 位验证码：").strip()
        print("\n=== 第 2 步：用验证码登录 ===")
        data = sms_login(phone, code)
        if not data:
            return 1
        token = data.get("access_token") or ""
        uid = data.get("uid")
        print("  [登录] uid=%s  is_guest=%s  is_adult=%s  phone=%s" % (
            uid, data.get("is_guest"), data.get("is_adult"), data.get("phone_number")))
        print("  [登录] access_token 长度=%d  前缀=%s..." % (len(token), token[:20]))
        if not token:
            print("  没有拿到 access_token —— 这条路线不成立")
            return 1
        json.dump({"access_token": token, "uc_account_token": data.get("uc_account_token"),
                   "uid": uid, "saved_at": int(time.time())},
                  open(TOKEN_FILE, "w", encoding="utf-8"), ensure_ascii=False)

    print("\n=== 第 3 步：用该 token 查 5 个池子 ===")
    out = {}
    total = 0
    for pid, pname in POOLS:
        r = fetch_pool(token, pid)
        if r["ok"]:
            out[str(pid)] = r["items"]
            total += r["count"]
            print("  [OK] %-6s type_id=%d -> %d 页 / %d 条" % (pname, pid, r["pages"], r["count"]))
        else:
            out[str(pid)] = []
            print("  [FAIL] %-6s type_id=%d -> %s" % (pname, pid, r["err"]))
    json.dump(out, open(RESULT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n记录已保存: %s" % RESULT_FILE)
    print("合计 %d 条" % total)
    if total == 0:
        print("注意：0 条可能是新号/未抽卡，也可能接口行为有差异，需人工判断")
    return 0


if __name__ == "__main__":
    sys.exit(main())
