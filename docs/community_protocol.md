# 少前 2 社区（BBS）签到 / 兑换协议

> 采集时间：2026-10-28 22:27（全局抓包，Edge 156，国服账号）
> 采集工具：`tools/capture/`（临时逆向用，不进产品），原始报文在 `.runtime/capture/community-20261028-2230/flows.jsonl`（含 30 天有效的社区 JWT，不要提交）

## 1. 域名与入口

| 用途 | 地址 |
| --- | --- |
| 社区页面 | `https://gf2-bbs.exiliumgf.com` |
| 社区 API | `https://gf2-bbs-api.exiliumgf.com` |
| 图片 CDN | `community-cdn.exiliumgf.com`、`community.cdn.sunborngame.com` |
| 官方区服接口（公告/横幅） | `gf2-zoneinfo.sunborngame.com` |

页面入口会带上游戏票据：

```
GET https://gf2-bbs.exiliumgf.com/loading?token=<urlencode(游戏 access_token)>
```

页面拿到 `token` 后调 `/login/game_skip` 换成社区 JWT，再开始正常请求。

## 2. 鉴权

- 社区全部业务接口用 JWT：`Authorization: <JWT>`（HS256，有效期 30 天，payload 含 `Id`/`OpenId`/`Platform`/`exp`）。
- 换票接口：`POST /login/game_skip`，body `{"game_token": "<游戏 access_token>"}`，返回 `data.account.token`（社区 JWT）、`uid`、`platform_id`。
- 游戏 access_token 就是现有登录链路产出的 `<base64(payload)>.<签名>`（手机号+短信 / 邮箱+密码，见 `GF2_SMS_LOGIN_PROTOCOL.md` §6、§8）。
- 请求只需 `Authorization` + `Content-Type: application/json`：**没有签名、没有时间戳、没有 CSRF token**；服务端 CORS 全开（`Access-Control-Allow-Origin: *`，允许 `Authorization` 头）。
- 两种令牌相互独立：游戏 access_token 单会话（再登录即作废），社区 JWT 独立 30 天。社区 JWT 泄漏即可签到/兑换（受积分与次数上限约束），只存本机、不要回传。

## 3. 接口清单

| 方法 | 路径 | 请求体 | 关键响应 |
| --- | --- | --- | --- |
| GET | `/community/task/get_current_sign_in_status` | – | `data.has_sign_in` |
| POST | `/community/task/sign_in` | `{}` | `get_exp`、`get_score`、`get_item_count`、`get_item_name`、`get_item_url`；重复签到 `Code=30010`「当日已签到」 |
| GET | `/community/item/exchange_list` | – | `data.list[]`：`exchange_id`、`item_name`、`item_count`、`use_score`、`exchange_count`、`max_exchange_count`、`cycle`(day/month)、`start_time`、`end_time` |
| POST | `/community/item/exchange` | `{"exchange_id": N}` | 成功 `data={}`；失败 `Code=30011`「兑换失败」 |
| POST | `/community/member/info` | `{}` | `data.user.score`（积分）、`exp`、`level`、`game_uid`、`nick_name` |
| POST | `/login/game_skip` | `{"game_token": "..."}` | `data.account.token/uid/platform_id` |

统一信封：`{"Code": 0, "Message": "OK", "data": ...}`，`Code != 0` 时 `Message` 是中文原因。

## 4. 实测流程（2026-10-28 22:27）

1. `get_current_sign_in_status` → `has_sign_in: false`
2. `sign_in` → `+40 积分`、`+55 exp`、`情报拼图 ×10`
3. `get_current_sign_in_status` → `has_sign_in: true`
4. `member/info` → `score: 540`
5. `exchange {exchange_id: 1}`（30 分）→ 成功，`score: 510`
6. `exchange {exchange_id: 2}`（30 分）→ 成功，`score: 480`
7. 重复签到探针 → `Code: 30010`；非法 `exchange_id: 9999` → `Code: 30011`

积分来源：签到 40/天；兑换消耗 30~100/次。

## 5. 当前兑换项（2026-10-28）

| exchange_id | 物品 | 数量 | 需要积分 | 周期 | 上限 |
| --- | --- | --- | --- | --- | --- |
| 1 | 情报拼图 | 10 | 30 | 日 | 2 |
| 2 | 萨狄斯金 | 500 | 30 | 日 | 1 |
| 3 | 战场报告 | 500 | 30 | 日 | 1 |
| 4 | 解析图纸 | 500 | 30 | 日 | 1 |
| 5 | 基原信息核 | 1 | 100 | 月 | 1 |

`exchange_count` 是**当前周期内已兑换次数**，本地要按 `cycle` 判断重置（日/月），不能只看数字。

## 5.1 每日任务（2026-10-28 22:35 抓包）

任务列表：`GET /community/task/get_current_task_list`（鉴权），返回：

| 分组 | 任务 | 奖励 | 次数 |
| --- | --- | --- | --- |
| daily_task | 浏览帖子 | 单次 +15 经验，完成 3 次后 +40 积分 | 3/日 |
| daily_task | 点赞帖子 | 单次 +10 经验，完成 3 次后 +40 积分 | 3/日 |
| daily_task | 分享帖子 | 完成后 +5 经验 +40 积分 | 1/日 |
| more_task | 设置个性签名 | 完成后 +20 经验 +40 积分 | 一次性 |

每项字段：`task_name`、`task_context`、`complete_count`、`max_complete_count`。**没有领取接口——动作即计数、达标即发奖**。

完成动作（都是 GET，带 `Authorization`）：

```
GET /community/topic/list?sort_type=1&category_id=1&query_type=1&last_tid=0&pub_time=0&reply_time=0&hot_value=0&update_time=0&is_new_mark=0
GET /community/topic/{tid}?id={tid}          # 浏览帖子（3 个不同 tid）
GET /community/topic/like/{tid}?id={tid}     # 点赞（3 个不同 tid）
GET /community/topic/share/{tid}?id={tid}    # 分享（1 次）
```

- 帖子详情返回 `is_like` / `is_favor` / `is_follow`，点赞前必须先判 `is_like == false`，否则会点成**取消点赞**。
- 实测收益：三个日常任务做完 `score 480 → 600`（+120 = 40×3）、`exp 13850 → 13930`（+80 = 15×3 + 10×3 + 5）。
- 月度签到日历另有接口 `GET /community/task/get_month_sign_in_status`（`end_date` + 奖励列表），本次未使用。

### 5.2 每日任务的防错与复核（实现层）

| 风险 | 处理 |
| --- | --- |
| 帖子不存在/已删除（实测 `20005`） | ID 只取列表接口刚返回的 `topic_id`，并过滤 `status != 0` 的条目；每条动作独立 try，单条失效只跳过，不中断整步 |
| 点赞点成取消 | 列表 `is_like` 预筛 → 详情再确认未赞 → 点赞 → **重新拉详情确认 `is_like == true`**，否则记「接口成功但未生效」并换下一篇；不给自己点赞 |
| 分享没生效 | 失败自动换下一篇；以任务列表 `分享帖子` 的 `complete_count` 增长作为落地凭据 |
| 动作做了但任务没算 | 收尾再拉一次任务列表，用 before/after 判定每个任务是否真完成；未完成在步骤里标红并列出剩余次数 |

## 6. 实现（PC 端，已完成）

- `backend/community.py`：协议客户端。`ensure_account()` 本地令牌失效时自动用游戏 access_token 走 `game_skip` 重换；`one_click()` 串起 签到 → 每日任务 → 兑换，每步失败单独记录不中断后续。
- `main.py`：`get_community_status` / `bind_community` / `community_one_click` 三个 pywebview API（已加入 `_create_js_api` 白名单）。
- `frontend/src/App.vue`：侧栏第 3 项「社区」，卡片显示昵称/积分/等级/令牌有效期/签到状态、任务进度、兑换清单和最近一次执行结果；按钮 = 刷新 / 绑定社区 / 一键签到+任务+兑换。
- 令牌落盘 `localdata/community.json`（已加入 `.gitignore`），字段 `token/uid/platform_id/channel_id/exp`。
- 兑换顺序（`DEFAULT_EXCHANGE_PLAN`）：基原信息核 → 情报拼图 ×2 → 萨狄斯金 → 战场报告 → 解析图纸；先查 `exchange_list` 与 `member_info.score` 本地预判，兑换次数用完/积分不足直接跳过，不硬打 `30011`。
- 图标名称随接口返回，不写死（2026-10-28 实测：`情报拼图/萨狄斯金/战场报告/解析图纸/基原信息核`）。

### 6.1 特殊情况处理

| 情况 | 行为 |
| --- | --- |
| 今天已签到 | `get_current_sign_in_status` 先判；接口回 `30010` 也当「已签到」，步骤标 `skip`，不报错 |
| 反复点一键 | 签到/任务幂等；兑换按 `exchange_count / max_exchange_count` 预判，兑换次数用完直接跳过；同一天第二次点只会得到「都做完了」 |
| 连点并发 | `threading.Lock` 非阻塞获取，正在跑时立刻返回「上一次一键完成还在执行」，不会并发扣积分 |
| 积分不够全部兑换 | **不中断计划**：按 基原信息核 → 情报拼图×2 → 萨狄斯金 → 战场报告 → 解析图纸 顺序换到换不动为止，提示「已兑换 N 项…；积分不足，还有 M 项没换」 |
| 积分完全不够 | 不调用任何兑换接口，提示「积分不足：现有 X 分，本轮没有可兑换的」 |
| 单步失败 | 该步标 `error` 并继续后面步骤，最后 `ok = all(step != error)` |

### 6.2 手机端（XKL_android，2026-10-29）

- `data/CommunityApi.kt`：同一套协议（换票 / 签到 / 每日任务 / 兑换 / 一键）。每日任务同样带 `20005` 单条跳过、点赞三重校验（列表 `is_like` → 详情 → 点后再拉详情复核）、分享后按任务 `complete_count` 增长判定。
- `data/CommunityStore.kt`：`files/community.json`，**按账号 key 存**社区 JWT（官服=uid、B服=bili:uid），切号各用各的票，不用重新绑定。
- `ui/CommunityActivity.kt` + `res/layout/activity_community.xml`：**独立页面**（不是弹窗），左上角返回按钮与 LoginActivity 一致；内容为纵向卡片（账号 / 每日任务 / 积分兑换 / 最近一次执行），底部固定金色「一键签到 + 任务 + 兑换」大按钮，上方是「刷新状态 / 重新绑定」。
- 入口：主界面「添加账号 / 管理账号 / 分享 / 刷新」那一排上方的**金色实底大按钮「社区签到」**（50dp，`bg_btn_gold`），只对官服显示；`MainActivity.renderAccountHeader()` 按 `GameChannel.OFFICIAL` 控制可见性，B 服直接隐藏。
- 按钮语义与 PC 一致——未绑定只露「绑定社区」且一键禁用，已绑定是「刷新状态 / 重新绑定 / 一键」；首次进页面不偷偷换票，只有「绑过但过期」才自动续期。
- 已知限制：游戏 access_token 是单会话的。旧票换票时 `game_skip` 会回 `token error`，已翻译成「游戏凭证已失效：请回主界面点『刷新』重新登录，再回来绑定社区」。
- 底部安全区：`ui/InsetSupport.kt` 的 `View.applyBottomSafeInset()` 给主界面（`main_root`）、登录页（`login_root`）、社区页底部按钮区（`community_bottom`）统一加 `max(系统导航栏 inset, 16dp)` 的底部留白。实测这台模拟器隐藏了导航栏（InsetsState 里只有 STATUS_BAR，没有 NAVIGATION_BAR 源），不补这一层的话底部固定按钮会贴在屏幕上滑手势区。

## 7. 未验证与风险

- 服务端是否校验 `Origin`/`Referer` 未单独验证（抓包里都带了；CORS 全开通常不校验）。
- `30011` 不区分「积分不足 / 次数用尽 / 商品下架」，实现时必须在本地预判并给出准确提示。
- 社区 JWT 过期后的续期完全依赖游戏 access_token；只在游戏内登录、没跑过抓包的用户拿不到 access_token。
- 同一账号重复调用 `sign_in` 是安全的（`30010`）；兑换必须先查列表，避免重复消耗积分。
