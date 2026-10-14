#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""抽卡记录接口调用：把捕获到的请求重放成五个池子的完整记录

与旧版的区别：所有失败都带结构化原因（kind / status / code / msg / pool），
界面才能给出可操作的提示，而不是把「token 过期」「网络失败」「接口变更」
统统显示成同一句「获取抽卡记录失败」。
"""
from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path

import aiohttp

try:
    from backend.capture import describe_capture, load_capture, save_capture
except ImportError:  # 兼容只把 backend 目录加进 sys.path 的调用方式
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from backend.capture import describe_capture, load_capture, save_capture

BASE_URL = "https://gf2-gacha-record.sunborngame.com/list"

# (池子类型ID, 展示名, 返回给前端的 key)
POOLS = (
    ("1", "常驻池", "permanent_pool"),
    ("3", "角色池", "character_pool"),
    ("4", "武器池", "weapon_pool"),
    ("6", "自选角色池", "custom_character_pool"),
    ("7", "自选武器池", "custom_weapon_pool"),
)

# 分页保护的页数上限，避免接口异常时无限翻页
MAX_PAGES = 200


def _error(kind: str, msg: str, *, status=None, code=None) -> dict:
    return {"kind": kind, "msg": msg, "status": status, "code": code}


def _with_page(error: dict, pool_name: str, page: int, ok_pages: int) -> dict:
    """给错误补上「在哪个池子、第几页断的」

    逐页成功的日志太吵（一个池子能有一百多页），所以只在出错时把中断位置
    记下来，用户/开发者一眼就能看到断在哪。
    """
    detail = f"{pool_name} 第 {page} 页中断（此前已成功 {ok_pages} 页）"
    print(f"[ERROR] {detail}：{error.get('msg')}")
    enriched = dict(error)
    enriched["pool"] = pool_name
    enriched["page"] = page
    enriched["ok_pages"] = ok_pages
    return enriched


def set_gacha_Banner(id, json_path=None):
    """设置抽卡池类型（文件版本，保留兼容性）

    目前主流程不用它（重放时直接改内存里的副本），保留给手工调试。
    """
    if json_path is not None:
        base_request = None
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                base_request = json.load(f)
        except Exception as e:
            print(f"[ERROR] 读取请求数据失败: {e}")
            return False
        base_request.setdefault("body", {})["type_id"] = id
        base_request["body"].pop("next", None)
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(base_request, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"[ERROR] 保存请求数据失败: {e}")
            return False

    base_request = load_capture()
    if not base_request:
        print("[ERROR] 请求数据不存在")
        return False
    base_request.setdefault("body", {})["type_id"] = id
    base_request["body"].pop("next", None)
    return save_capture(base_request, source="set_gacha_Banner").get("saved", False)


# 每页条数：官方接口默认只给 6 条，实测 limit 最大有效值 20。
# 加上它，五池并发拉取的总耗时从 ~12s 降到 ~3s。
PAGE_SIZE = "20"


def _set_gacha_banner_dict(request_data, pool_type_id):
    """设置抽卡池类型（内存版本）"""
    body = request_data.setdefault("body", {})
    body["type_id"] = pool_type_id
    body["limit"] = PAGE_SIZE
    body.pop("next", None)
    return request_data


async def _request_page_async(request_data, session) -> dict:
    """请求单页数据，返回 {"ok": True, "json": ...} 或 {"ok": False, "error": {...}}"""
    body = request_data.setdefault("body", {})
    params = request_data.get("params") or {}
    headers = dict(request_data.get("headers") or {})
    # 说明：Content-Length 交给 aiohttp 按真实表单体计算（手算版本在加了 limit 后会算错）
    headers.pop("Content-Length", None)

    try:
        async with session.post(
            url=BASE_URL,
            params=params,
            data=body,
            headers=headers,
            ssl=False,
            allow_redirects=False,
        ) as response:
            status = response.status
            text = await response.text()
    except Exception as e:
        return {"ok": False, "error": _error("network", f"请求失败: {e}")}

    if status != 200:
        preview = (text or "").strip().replace("\n", " ")[:120]
        return {"ok": False, "error": _error("http", f"服务器返回 HTTP {status} {preview}", status=status)}

    try:
        payload = json.loads(text)
    except Exception:
        preview = (text or "").strip().replace("\n", " ")[:120]
        return {"ok": False, "error": _error("parse", f"返回内容不是 JSON（可能被代理/防火墙改写）: {preview}", status=status)}

    if not isinstance(payload, dict):
        return {"ok": False, "error": _error("parse", "返回内容结构异常", status=status)}

    code = payload.get("code")
    if code != 0:
        # 注意：接口的真实字段是 message，msg 只是某些接口的别名（原来只读 msg，导致错误全变成"无描述"）
        detail = payload.get("msg") or payload.get("message") or "无描述"
        return {"ok": False, "error": _error("api", f"接口返回 code={code}：{detail}", status=status, code=code)}

    data = payload.get("data")
    if not isinstance(data, dict) or "next" not in data:
        return {"ok": False, "error": _error("parse", "返回内容缺少分页字段 next", status=status, code=code)}

    next_value = data.get("next") or ""
    if next_value:
        body["next"] = next_value
    else:
        body.pop("next", None)

    return {"ok": True, "json": payload}


async def get_gacha_pool_async(pool_type_id, pool_name, session, base_request) -> dict:
    """获取单个池子的所有分页数据

    Returns:
        {"ok": True, "pages": [...]} 或 {"ok": False, "error": {...}}
    """
    request_data = copy.deepcopy(base_request)
    _set_gacha_banner_dict(request_data, pool_type_id)

    result = await _request_page_async(request_data, session)
    if not result["ok"]:
        return {"ok": False, "error": _with_page(result["error"], pool_name, 1, 0)}

    pages = [result["json"]]

    # 中间页不再逐页打日志（一个池子可能一百多页），只在最后汇总 +
    # 出问题时记录中断在第几页
    page = 2
    while True:
        next_value = (pages[-1].get("data") or {}).get("next") or ""
        if not next_value:
            break
        if page > MAX_PAGES:
            return {
                "ok": False,
                "error": _with_page(
                    _error("pagination", f"分页超过 {MAX_PAGES} 页，疑似接口异常"),
                    pool_name, page, len(pages),
                ),
            }

        result = await _request_page_async(request_data, session)
        if not result["ok"]:
            return {"ok": False, "error": _with_page(result["error"], pool_name, page, len(pages))}
        pages.append(result["json"])
        page += 1

    total = sum(len((item.get("data") or {}).get("list") or []) for item in pages)
    print(f"[OK] {pool_name}完成：{len(pages)} 页 / {total} 条记录")
    return {"ok": True, "pages": pages}


async def _get_all_pools_async(base_request):
    """并行获取所有池子数据"""
    async with aiohttp.ClientSession() as session:
        return await asyncio.gather(
            *[
                get_gacha_pool_async(pool_type_id, pool_name, session, base_request)
                for pool_type_id, pool_name, _ in POOLS
            ]
        )


def get_gacha_data_all_ex() -> dict:
    """获取五个池子的抽卡数据，失败时带结构化原因

    Returns:
        {"ok": True, "data": {...}, "error": None}
        {"ok": False, "data": None, "error": {"kind": ..., "msg": ...}}
    """
    base_request = load_capture()
    if not base_request:
        return {
            "ok": False,
            "data": None,
            "error": _error("no_capture", "捕获文件不存在或为空，还没有抓到游戏请求"),
        }

    print("[INFO] 开始并行获取五个池子的数据...")
    try:
        results = asyncio.run(_get_all_pools_async(base_request))
    except Exception as e:
        print(f"[ERROR] 获取抽卡数据异常: {e}")
        return {"ok": False, "data": None, "error": _error("internal", f"内部异常: {e}")}

    data = {}
    first_error = None
    for (_, pool_name, key), result in zip(POOLS, results):
        if result.get("ok"):
            data[key] = result["pages"]
        elif first_error is None:
            first_error = dict(result.get("error") or _error("unknown", "未知错误"))
            first_error["pool"] = pool_name

    if first_error is not None:
        print(f"[ERROR] 部分池子数据获取失败: {first_error}")
        return {"ok": False, "data": None, "error": first_error}

    print("[OK] 所有池子数据获取完成")
    return {"ok": True, "data": data, "error": None}


def get_gacha_data_all():
    """兼容旧接口：成功返回数据，失败返回 None"""
    return get_gacha_data_all_ex().get("data")


if __name__ == "__main__":
    print(json.dumps(describe_capture(), ensure_ascii=False, indent=2))
    outcome = get_gacha_data_all_ex()
    print(json.dumps(outcome.get("error"), ensure_ascii=False) if not outcome.get("ok") else "[OK] 获取成功")
