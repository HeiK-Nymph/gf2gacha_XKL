#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""少前 2 社区（BBS）：签到 / 每日任务 / 积分兑换。

协议来源：docs/community_protocol.md（2026-10-28 全局抓包实测）。
鉴权：用游戏 access_token 调 POST /login/game_skip 换社区 JWT（30 天），
      之后所有请求只需要 `Authorization` + JSON，没有签名、时间戳或 CSRF。

落盘：localdata/community.json（只有本机可见，别提交；内含 30 天有效 JWT）。

设计约束（用户拍板）：
    * 复用游戏 access_token 换票，不让用户单独登录一次社区；
    * 一键流程 = 签到 → 每日任务 → 兑换，全部由按钮触发，不做后台常驻定时；
    * 兑换优先级：本源信息核 → 情报拼图 ×2 → 萨迪斯金 → 战场报告 → 武器图纸。
"""
from __future__ import annotations

import base64
import json
import os
import sys
import threading
import time
from pathlib import Path

import requests

API_BASE = "https://gf2-bbs-api.exiliumgf.com"
TIMEOUT = 15

# 兑换优先级（用户指定）：(exchange_id, 次数)
DEFAULT_EXCHANGE_PLAN = ((5, 1), (1, 2), (2, 1), (3, 1), (4, 1))

# 业务错误码（实测）
CODE_SIGNED_TODAY = 30010  # 当日已签到
CODE_EXCHANGE_FAILED = 30011  # 兑换失败（积分不足 / 次数用完 / 商品下架都归到这里）


class CommunityError(RuntimeError):
    """业务错误：message 直接给用户看。"""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code


# --------------------------------------------------------------------------- #
# 本地存储
# --------------------------------------------------------------------------- #
def _data_dir() -> Path:
    override = os.environ.get("GF2XKL_DATA_DIR", "").strip()
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent.parent.parent / "localdata"
    return Path(__file__).resolve().parent.parent / "localdata"


def account_path() -> Path:
    return _data_dir() / "community.json"


def load_account() -> dict:
    try:
        data = json.loads(account_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_account(data: dict) -> None:
    path = account_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["saved_at"] = int(time.time())
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def clear_account() -> None:
    try:
        account_path().unlink(missing_ok=True)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def jwt_payload(token: str) -> dict:
    try:
        part = (token or "").split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part).decode("utf-8", "replace"))
    except Exception:
        return {}


def jwt_exp(token: str) -> int:
    try:
        return int(jwt_payload(token).get("exp") or 0)
    except (TypeError, ValueError):
        return 0


def token_valid(account: dict, *, skew: int = 120) -> bool:
    token = str((account or {}).get("token") or "")
    exp = jwt_exp(token)
    return bool(token) and exp > time.time() + skew


def _fmt_ts(ts: int) -> str:
    if not ts:
        return "未知"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def _api(method: str, path: str, *, token: str = "", body=None, params=None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "GF2GachaXKL/1.0 (community)",
    }
    if token:
        headers["Authorization"] = token

    url = API_BASE + path
    try:
        resp = requests.request(
            method, url, headers=headers, json=body, params=params, timeout=TIMEOUT
        )
    except requests.RequestException as exc:
        raise CommunityError(f"社区接口连接失败：{exc}") from exc

    if resp.status_code == 401:
        raise CommunityError("社区令牌已失效，请重新绑定", 401)
    try:
        data = resp.json()
    except ValueError:
        raise CommunityError(f"社区接口返回异常（HTTP {resp.status_code}）") from None

    code = data.get("Code", data.get("code"))
    if code not in (0, None):
        message = str(data.get("Message") or data.get("message") or f"接口返回 {code}")
        raise CommunityError(message, code)
    payload = data.get("data")
    return payload if isinstance(payload, dict) else {}


# --------------------------------------------------------------------------- #
# 绑定 / 令牌
# --------------------------------------------------------------------------- #
def game_token_from_capture() -> str:
    """从最近一次抓到的游戏请求里取 access_token（Authorization 头）。"""
    try:
        from backend.capture import load_capture

        data = load_capture() or {}
        headers = data.get("headers") or {}
        for key, value in headers.items():
            if str(key).lower() == "authorization" and value:
                return str(value).strip()
    except Exception as exc:
        print(f"[community] 读取游戏凭证失败: {exc}")
    return ""


def bind(game_token: str | None = None) -> dict:
    """用游戏 access_token 换社区 JWT 并落盘。"""
    token = (game_token or "").strip() or game_token_from_capture()
    if not token:
        raise CommunityError("没有可用的游戏凭证：请先在游戏里打开「招募 · 访问详情」，回到工具点一次『更新记录』")

    data = _api("POST", "/login/game_skip", body={"game_token": token})
    account = data.get("account") or {}
    if not account.get("token"):
        raise CommunityError("社区登录失败：没有拿到令牌")

    record = {
        "token": account.get("token"),
        "uid": account.get("uid"),
        "platform_id": account.get("platform_id"),
        "channel_id": account.get("channel_id"),
        "exp": jwt_exp(account.get("token")),
        "bound_at": int(time.time()),
    }
    save_account(record)
    print(f"[community] 已绑定社区账号 uid={record.get('uid')}，令牌有效期到 {_fmt_ts(record['exp'])}")
    return record


def ensure_account() -> dict:
    """拿可用账号：本地令牌有效就直接用，过期了用游戏凭证重换。"""
    account = load_account()
    if token_valid(account):
        return account
    print("[community] 社区令牌缺失或已过期，尝试用游戏凭证重新换票")
    return bind()


# --------------------------------------------------------------------------- #
# 账号信息 / 签到
# --------------------------------------------------------------------------- #
def member_info(token: str) -> dict:
    return _api("POST", "/community/member/info", token=token, body={}).get("user") or {}


def sign_status(token: str) -> bool:
    data = _api("GET", "/community/task/get_current_sign_in_status", token=token)
    return bool(data.get("has_sign_in"))


def sign_in(token: str) -> dict:
    return _api("POST", "/community/task/sign_in", token=token, body={})


# --------------------------------------------------------------------------- #
# 每日任务
# --------------------------------------------------------------------------- #
def task_list(token: str) -> dict:
    return _api("GET", "/community/task/get_current_task_list", token=token)


def _topic_list(token: str) -> list[dict]:
    params = {
        "sort_type": 1,
        "category_id": 1,
        "query_type": 1,
        "last_tid": 0,
        "pub_time": 0,
        "reply_time": 0,
        "hot_value": 0,
        "update_time": 0,
        "is_new_mark": 0,
    }
    data = _api("GET", "/community/topic/list", token=token, params=params)
    return [item for item in (data.get("list") or []) if item.get("topic_id")]


def _topic_detail(token: str, tid: int) -> dict:
    return _api("GET", f"/community/topic/{tid}", token=token, params={"id": tid})


def _topic_like(token: str, tid: int) -> dict:
    return _api("GET", f"/community/topic/like/{tid}", token=token, params={"id": tid})


def _topic_share(token: str, tid: int) -> dict:
    return _api("GET", f"/community/topic/share/{tid}", token=token, params={"id": tid})


def _attempt(call, *args):
    """执行一次动作，返回 (结果, 错误)；单条失败不抛给上层，便于逐条跳过。"""
    try:
        return call(*args), None
    except CommunityError as exc:
        return None, exc


def _usable_topics(token: str) -> list[dict]:
    """只挑刚拉到、status=0 的正常帖子，避免拿陈旧 ID 去撞「帖子不存在」。"""
    topics = []
    for item in _topic_list(token):
        if not item.get("topic_id"):
            continue
        if str(item.get("status", 0)) not in ("0", "None"):
            continue
        topics.append(item)
    return topics


def complete_daily_tasks(token: str) -> dict:
    """把今天的浏览/点赞/分享任务补齐（动作即计数，没有领取接口）。

    防「进不存在的帖子」：帖子 ID 一律来自刚返回的列表，逐条 try 掉
    20005「帖子不存在或已删除」，单条失效只跳过、不拖垮整步。
    防「假点赞」：点前查详情 is_like，点完再拉详情复核；分享后用任务次数
    增长作为落地凭据。最终以任务进度（before/after）作为完成依据。
    """
    before = task_list(token)
    need: dict[str, int] = {}
    for item in before.get("daily_task") or []:
        name = str(item.get("task_name") or "")
        left = int(item.get("max_complete_count") or 0) - int(item.get("complete_count") or 0)
        need[name] = max(0, left)

    topics = _usable_topics(token)
    if not topics:
        raise CommunityError("社区帖子列表为空，暂时无法完成任务")

    actions: list[str] = []
    skipped: list[str] = []
    my_uid = int(load_account().get("uid") or 0)

    # 1) 浏览帖子：每篇只打开一次，打不开就换下一篇
    browse_left = need.get("浏览帖子", 0)
    for item in topics:
        if browse_left <= 0:
            break
        tid = int(item["topic_id"])
        detail, exc = _attempt(_topic_detail, token, tid)
        if detail is None:
            skipped.append(f"浏览 {tid}：{exc.message}")
            continue
        browse_left -= 1
        actions.append(f"浏览帖子 {tid}")

    # 2) 点赞帖子：列表预筛 → 详情确认未赞 → 点赞 → 详情复核已赞
    like_left = need.get("点赞帖子", 0)
    for item in topics:
        if like_left <= 0:
            break
        tid = int(item["topic_id"])
        if item.get("is_like"):
            continue
        if my_uid and int(item.get("user_id") or 0) == my_uid:
            continue  # 不给自己点赞
        detail, exc = _attempt(_topic_detail, token, tid)
        if detail is None:
            skipped.append(f"点赞 {tid}：{exc.message}")
            continue
        if detail.get("is_like"):
            continue
        _, exc = _attempt(_topic_like, token, tid)
        if exc is not None:
            skipped.append(f"点赞 {tid}：{exc.message}")
            continue
        verified, _ = _attempt(_topic_detail, token, tid)
        if not (verified or {}).get("is_like"):
            skipped.append(f"点赞 {tid}：接口成功但未生效")
            continue
        like_left -= 1
        actions.append(f"点赞帖子 {tid}")

    # 3) 分享帖子：一天一次；失败换下一篇，成功后用任务次数复核
    if need.get("分享帖子", 0) > 0:
        for item in topics:
            tid = int(item["topic_id"])
            _, exc = _attempt(_topic_share, token, tid)
            if exc is not None:
                skipped.append(f"分享 {tid}：{exc.message}")
                continue
            actions.append(f"分享帖子 {tid}")
            break

    after = task_list(token)
    progress: dict[str, dict] = {}
    for item in after.get("daily_task") or []:
        name = str(item.get("task_name") or "")
        done = int(item.get("complete_count") or 0)
        total = int(item.get("max_complete_count") or 0)
        prev = next(
            (int(x.get("complete_count") or 0) for x in before.get("daily_task") or [] if str(x.get("task_name")) == name),
            0,
        )
        progress[name] = {
            "before": prev,
            "after": done,
            "max": total,
            "gained": done - prev,
            "done": done >= total,
        }

    return {"actions": actions, "skipped": skipped, "progress": progress, "tasks": after}


# --------------------------------------------------------------------------- #
# 积分兑换
# --------------------------------------------------------------------------- #
def exchange_list(token: str) -> list[dict]:
    return _api("GET", "/community/item/exchange_list", token=token).get("list") or []


def exchange(token: str, exchange_id: int) -> dict:
    return _api("POST", "/community/item/exchange", token=token, body={"exchange_id": int(exchange_id)})


def run_exchange_plan(token: str, plan=DEFAULT_EXCHANGE_PLAN) -> dict:
    """按优先级兑换；先查列表与积分，避免把 30011 当唯一反馈。

    积分不够时**不中断计划**：继续往下看低优先级的项，直到一项都换不动为止，
    调用方根据 skipped 里的 reason 给用户分档提示。
    """
    items = {int(item.get("exchange_id")): item for item in exchange_list(token)}
    score_before = int((member_info(token) or {}).get("score") or 0)
    score = score_before
    results: list[dict] = []
    skipped: list[dict] = []

    for exchange_id, times in plan:
        item = items.get(exchange_id)
        if not item:
            skipped.append({"exchange_id": exchange_id, "name": f"#{exchange_id}", "reason": "missing", "detail": "不在兑换列表"})
            continue
        name = str(item.get("item_name") or f"#{exchange_id}")
        total = int(item.get("max_exchange_count") or 0)
        used = int(item.get("exchange_count") or 0)
        left = max(total - used, 0)
        cost = int(item.get("use_score") or 0)
        want = min(int(times), left)
        if want <= 0:
            skipped.append({"exchange_id": exchange_id, "name": name, "reason": "sold_out", "detail": f"本期兑换次数已用完（{used}/{total}）"})
            continue

        for _ in range(want):
            if score < cost:
                skipped.append({"exchange_id": exchange_id, "name": name, "reason": "no_score", "detail": f"积分不足（{score} < {cost}）"})
                break
            try:
                exchange(token, exchange_id)
            except CommunityError as exc:
                skipped.append({"exchange_id": exchange_id, "name": name, "reason": "error", "detail": exc.message})
                break
            score -= cost
            results.append(
                {
                    "exchange_id": exchange_id,
                    "name": name,
                    "count": int(item.get("item_count") or 0),
                    "cost": cost,
                    "cycle": item.get("cycle"),
                }
            )

    return {
        "exchanged": results,
        "skipped": skipped,
        "score_before": score_before,
        "score_left": score,
        "spent": score_before - score,
    }


def _exchange_message(data: dict) -> str:
    exchanged = data.get("exchanged") or []
    skipped = data.get("skipped") or []
    low_score = [item for item in skipped if item.get("reason") == "no_score"]
    sold_out = [item for item in skipped if item.get("reason") == "sold_out"]
    errors = [item for item in skipped if item.get("reason") == "error"]

    parts: list[str] = []
    if exchanged:
        detail = "、".join(f"{item['name']}×{item['count']}" for item in exchanged)
        parts.append(f"已兑换 {len(exchanged)} 项：{detail}（消耗 {data.get('spent', 0)} 分，剩余 {data.get('score_left', 0)} 分）")
        if low_score:
            parts.append(f"积分不足，还有 {len(low_score)} 项没换（{low_score[0]['name']} 起）")
    elif low_score and not errors:
        parts.append(f"积分不足：现有 {data.get('score_left', 0)} 分，本轮没有可兑换的")
    elif sold_out and not errors:
        parts.append("今天的兑换次数用完了，明天再来")

    if sold_out and exchanged:
        parts.append(f"另有 {len(sold_out)} 项本轮兑换次数已用完")
    if errors:
        parts.append("失败：" + "；".join(f"{item['name']}：{item['detail']}" for item in errors))

    return "；".join(parts) if parts else "没有可兑换的东西"


# --------------------------------------------------------------------------- #
# 对外快照 / 一键
# --------------------------------------------------------------------------- #
def snapshot(token: str) -> dict:
    user = member_info(token)
    tasks = task_list(token)
    exchange_items = exchange_list(token)
    return {
        "ok": True,
        "bound": True,
        "uid": user.get("uid"),
        "nick_name": user.get("nick_name") or user.get("game_nick_name") or "",
        "avatar": user.get("avatar") or "",
        "score": user.get("score"),
        "exp": user.get("exp"),
        "level": user.get("level"),
        "game_uid": user.get("game_uid"),
        "game_commander_level": user.get("game_commander_level"),
        "signed_in": sign_status(token),
        "token_exp": _fmt_ts(jwt_exp(token)),
        "token_exp_ts": jwt_exp(token),
        "tasks": {
            "daily": tasks.get("daily_task") or [],
            "more": tasks.get("more_task") or [],
        },
        "exchange": exchange_items,
    }


def _safe_snapshot(token: str) -> dict:
    """snapshot 不抛异常：界面刷新失败时保留可用信息。"""
    try:
        return snapshot(token)
    except CommunityError as exc:
        return {"ok": False, "bound": True, "error": exc.message}


_running_lock = threading.Lock()


def one_click() -> dict:
    """按钮入口：签到 → 每日任务 → 兑换。每一步失败都记录，不中途放弃后面的步骤。

    用户可以反复点：
        * 签到/任务本身幂等（已签到返回 30010、任务满次数就不再动作）；
        * 兑换按 `exchange_count / max_exchange_count` 预判，兑换次数用完的直接跳过；
        * 正在执行时再点会立刻返回提示，不会并发扣积分。
    """
    if not _running_lock.acquire(blocking=False):
        raise CommunityError("上一次「一键完成」还在执行，请稍等几秒")
    try:
        return _one_click_locked()
    finally:
        _running_lock.release()


def _one_click_locked() -> dict:
    steps: list[dict] = []
    account = ensure_account()
    token = str(account.get("token") or "")
    if not token:
        raise CommunityError("社区未绑定：请先更新一次游戏记录以获取凭证")

    # 1) 签到
    try:
        if sign_status(token):
            steps.append({"name": "签到", "status": "skip", "message": "今天已经签过了"})
        else:
            data = sign_in(token)
            steps.append(
                {
                    "name": "签到",
                    "status": "ok",
                    "message": f"+{data.get('get_score', 0)} 积分、+{data.get('get_exp', 0)} 经验"
                    + (f"，{data.get('get_item_name')} ×{data.get('get_item_count')}" if data.get("get_item_name") else ""),
                }
            )
    except CommunityError as exc:
        if exc.code == CODE_SIGNED_TODAY:
            steps.append({"name": "签到", "status": "skip", "message": "今天已经签过了"})
        else:
            steps.append({"name": "签到", "status": "error", "message": exc.message})

    # 2) 每日任务
    try:
        data = complete_daily_tasks(token)
        actions = data.get("actions") or []
        progress = data.get("progress") or {}
        unfinished = [f"{name} {info['after']}/{info['max']}" for name, info in progress.items() if not info.get("done")]
        if actions:
            message = "、".join(actions)
            if unfinished:
                message += "；未完成：" + "、".join(unfinished)
        else:
            message = "今天的任务已经完成了" if not unfinished else "没有可执行的动作：" + "、".join(unfinished)
        if data.get("skipped"):
            message += "；跳过：" + "；".join(data["skipped"][:2])
            if len(data["skipped"]) > 2:
                message += f" 等 {len(data['skipped'])} 条"
        status = "ok" if actions and not unfinished else ("skip" if not actions and not unfinished else "error")
        steps.append({"name": "每日任务", "status": status, "message": message})
    except CommunityError as exc:
        steps.append({"name": "每日任务", "status": "error", "message": exc.message})

    # 3) 兑换（积分不够不会中断，按优先级一路换到换不动为止）
    try:
        data = run_exchange_plan(token)
        steps.append({"name": "兑换", "status": "ok" if data["exchanged"] else "skip", "message": _exchange_message(data)})
    except CommunityError as exc:
        steps.append({"name": "兑换", "status": "error", "message": exc.message})

    return {"ok": all(step["status"] != "error" for step in steps), "steps": steps, "account": _safe_snapshot(token)}
