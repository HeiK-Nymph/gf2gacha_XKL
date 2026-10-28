package uk.gf2gacha.xkl.data

import android.util.Base64
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/** 社区接口返回 Code != 0 或网络异常；30010=当日已签到，30011=兑换失败，20005=帖子不存在 */
class CommunityException(val code: Int, message: String) : Exception(message)

data class CommunityToken(val token: String, val uid: Long, val platformId: Long, val exp: Long) {
    fun isValid(nowSeconds: Long = System.currentTimeMillis() / 1000): Boolean =
        token.isNotEmpty() && exp > nowSeconds + 120
}

data class CommunityUser(
    val uid: Long,
    val nickName: String,
    val score: Int,
    val exp: Int,
    val level: Int,
    val signedIn: Boolean
)

data class CommunityTask(val name: String, val done: Int, val max: Int)

data class CommunityReward(
    val exchangeId: Int,
    val name: String,
    val count: Int,
    val score: Int,
    val exchanged: Int,
    val max: Int,
    val cycle: String
)

/** status: ok / skip / error，与 PC 端「最近一次执行」口径一致 */
data class CommunityStep(val name: String, val status: String, val message: String)

data class CommunitySnapshot(
    val user: CommunityUser,
    val tasks: List<CommunityTask>,
    val rewards: List<CommunityReward>
)

/**
 * 少前 2 社区（BBS）接口。协议见仓库 docs/community_protocol.md（2026-10-28 实测）。
 *
 * 鉴权：用游戏 access_token 调 /login/game_skip 换社区 JWT（30 天），
 * 之后所有请求只需要 Authorization + JSON，没有签名或 CSRF。
 * **只适用于官服账号**：B 服账号是 B 站登录，拿不到官方 access_token。
 */
object CommunityApi {

    private const val BASE = "https://gf2-bbs-api.exiliumgf.com"
    private val JSON_TYPE = "application/json; charset=utf-8".toMediaType()
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    /** 与 PC 端一致：基原信息核 → 情报拼图 ×2 → 萨狄斯金 → 战场报告 → 解析图纸 */
    val EXCHANGE_PLAN: List<Pair<Int, Int>> = listOf(5 to 1, 1 to 2, 2 to 1, 3 to 1, 4 to 1)

    fun jwtExp(token: String): Long = try {
        val part = token.split(".").getOrNull(1).orEmpty()
        val bytes = Base64.decode(part, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
        JSONObject(String(bytes, Charsets.UTF_8)).optLong("exp", 0L)
    } catch (e: Exception) {
        0L
    }

    /** 用游戏 access_token 换社区 JWT */
    fun bind(gameToken: String): CommunityToken {
        val body = JSONObject().put("game_token", gameToken)
        val data = try {
            call("POST", "/login/game_skip", body = body)
        } catch (e: CommunityException) {
            // 游戏凭证是单会话的：别处再登录一次，旧 token 就会失效，这里翻译成人话
            if (e.message?.contains("token", ignoreCase = true) == true) {
                throw CommunityException(401, "游戏凭证已失效：请回主界面点「刷新」重新登录，再回来绑定社区")
            }
            throw e
        }
        val account = data.optJSONObject("account") ?: throw CommunityException(0, "社区登录失败：没有拿到令牌")
        val token = account.optString("token")
        if (token.isEmpty()) throw CommunityException(0, "社区登录失败：没有拿到令牌")
        return CommunityToken(
            token = token,
            uid = account.optLong("uid", 0L),
            platformId = account.optLong("platform_id", 0L),
            exp = jwtExp(token)
        )
    }

    fun snapshot(token: CommunityToken): CommunitySnapshot {
        val userObj = call("POST", "/community/member/info", token = token.token, body = JSONObject())
            .optJSONObject("user") ?: JSONObject()
        val signedIn = call("GET", "/community/task/get_current_sign_in_status", token = token.token)
            .optBoolean("has_sign_in", false)
        return CommunitySnapshot(
            user = CommunityUser(
                uid = userObj.optLong("uid", token.uid),
                nickName = userObj.optString("nick_name"),
                score = userObj.optInt("score"),
                exp = userObj.optInt("exp"),
                level = userObj.optInt("level"),
                signedIn = signedIn
            ),
            tasks = taskProgress(token),
            rewards = exchangeList(token)
        )
    }

    fun taskProgress(token: CommunityToken): List<CommunityTask> {
        val data = call("GET", "/community/task/get_current_task_list", token = token.token)
        val out = mutableListOf<CommunityTask>()
        for (field in listOf("daily_task", "more_task")) {
            val array = data.optJSONArray(field) ?: continue
            for (i in 0 until array.length()) {
                val obj = array.optJSONObject(i) ?: continue
                out += CommunityTask(
                    name = obj.optString("task_name"),
                    done = obj.optInt("complete_count"),
                    max = obj.optInt("max_complete_count")
                )
            }
        }
        return out
    }

    fun exchangeList(token: CommunityToken): List<CommunityReward> {
        val array = call("GET", "/community/item/exchange_list", token = token.token)
            .optJSONArray("list") ?: return emptyList()
        return (0 until array.length()).mapNotNull { index ->
            val obj = array.optJSONObject(index) ?: return@mapNotNull null
            CommunityReward(
                exchangeId = obj.optInt("exchange_id"),
                name = obj.optString("item_name"),
                count = obj.optInt("item_count"),
                score = obj.optInt("use_score"),
                exchanged = obj.optInt("exchange_count"),
                max = obj.optInt("max_exchange_count"),
                cycle = obj.optString("cycle")
            )
        }
    }

    /**
     * 一键流程：签到 → 每日任务 → 兑换。
     * 每一步失败都记录，不中断后面的步骤（与 PC 端一致）。
     */
    fun oneClick(token: CommunityToken): Pair<Boolean, List<CommunityStep>> {
        val steps = mutableListOf<CommunityStep>()

        steps += try {
            if (call("GET", "/community/task/get_current_sign_in_status", token = token.token)
                    .optBoolean("has_sign_in", false)
            ) {
                CommunityStep("签到", "skip", "今天已经签过了")
            } else {
                val data = call("POST", "/community/task/sign_in", token = token.token, body = JSONObject())
                val item = data.optString("get_item_name")
                val extra = if (item.isNotEmpty()) "，$item ×${data.optInt("get_item_count")}" else ""
                CommunityStep(
                    "签到",
                    "ok",
                    "+${data.optInt("get_score")} 积分、+${data.optInt("get_exp")} 经验$extra"
                )
            }
        } catch (e: CommunityException) {
            if (e.code == 30010) CommunityStep("签到", "skip", "今天已经签过了")
            else CommunityStep("签到", "error", e.message ?: "签到失败")
        }

        steps += try {
            completeDailyTasks(token)
        } catch (e: CommunityException) {
            CommunityStep("每日任务", "error", e.message ?: "每日任务失败")
        }

        steps += try {
            runExchangePlan(token)
        } catch (e: CommunityException) {
            CommunityStep("兑换", "error", e.message ?: "兑换失败")
        }

        return steps.none { it.status == "error" } to steps
    }

    /**
     * 每日任务：浏览 3 次 / 点赞 3 次 / 分享 1 次。
     *
     * 防错与复核（与 PC 端一致）：
     *  - 帖子 ID 只取刚返回的列表，过滤 status != 0；单条 20005 只跳过，不中断；
     *  - 点赞前查详情 is_like，点完再拉详情复核 is_like=true，否则记为未生效；
     *  - 分享失败换下一篇；最后用任务 complete_count 的 before/after 判定是否真完成。
     */
    fun completeDailyTasks(token: CommunityToken): CommunityStep {
        val before = taskProgress(token)
        val need = mutableMapOf<String, Int>()
        for (task in before) need[task.name] = (task.max - task.done).coerceAtLeast(0)

        val topics = topicList(token).filter {
            it.optLong("topic_id") > 0 && it.optInt("status", 0) == 0
        }
        if (topics.isEmpty()) throw CommunityException(0, "社区帖子列表为空，暂时无法完成任务")

        val actions = mutableListOf<String>()
        val skipped = mutableListOf<String>()

        // 1) 浏览帖子
        var browseLeft = need["浏览帖子"] ?: 0
        for (item in topics) {
            if (browseLeft <= 0) break
            val tid = item.optLong("topic_id")
            try {
                topicDetail(token, tid)
            } catch (e: CommunityException) {
                skipped += "浏览 $tid：${e.message}"
                continue
            }
            browseLeft--
            actions += "浏览帖子 $tid"
        }

        // 2) 点赞帖子（三重校验）
        var likeLeft = need["点赞帖子"] ?: 0
        for (item in topics) {
            if (likeLeft <= 0) break
            val tid = item.optLong("topic_id")
            if (item.optBoolean("is_like", false)) continue
            if (token.uid > 0 && item.optLong("user_id", 0L) == token.uid) continue
            val detail = try {
                topicDetail(token, tid)
            } catch (e: CommunityException) {
                skipped += "点赞 $tid：${e.message}"
                continue
            }
            if (detail.optBoolean("is_like", false)) continue
            try {
                topicLike(token, tid)
            } catch (e: CommunityException) {
                skipped += "点赞 $tid：${e.message}"
                continue
            }
            val verified = try {
                topicDetail(token, tid).optBoolean("is_like", false)
            } catch (e: CommunityException) {
                false
            }
            if (!verified) {
                skipped += "点赞 $tid：接口成功但未生效"
                continue
            }
            likeLeft--
            actions += "点赞帖子 $tid"
        }

        // 3) 分享帖子
        val shareLeft = need["分享帖子"] ?: 0
        if (shareLeft > 0) {
            for (item in topics) {
                val tid = item.optLong("topic_id")
                try {
                    topicShare(token, tid)
                    actions += "分享帖子 $tid"
                    break
                } catch (e: CommunityException) {
                    skipped += "分享 $tid：${e.message}"
                }
            }
        }

        val after = taskProgress(token)
        val unfinished = before.mapNotNull { old ->
            val now = after.firstOrNull { it.name == old.name } ?: return@mapNotNull null
            if (now.done >= now.max) null else "${now.name} ${now.done}/${now.max}"
        }

        val message = buildString {
            append(if (actions.isEmpty()) "今天的任务已经完成了" else actions.joinToString("、"))
            if (unfinished.isNotEmpty()) append("；未完成：").append(unfinished.joinToString("、"))
            if (skipped.isNotEmpty()) append("；跳过：").append(skipped.take(2).joinToString("；"))
        }
        val status = when {
            actions.isNotEmpty() && unfinished.isEmpty() -> "ok"
            actions.isEmpty() && unfinished.isEmpty() -> "skip"
            else -> "error"
        }
        return CommunityStep("每日任务", status, message)
    }

    /** 按优先级兑换；积分不足不会中断计划，换到换不动为止 */
    fun runExchangePlan(token: CommunityToken): CommunityStep {
        val rewards = exchangeList(token)
        var score = call("POST", "/community/member/info", token = token.token, body = JSONObject())
            .optJSONObject("user")?.optInt("score") ?: 0
        val scoreBefore = score
        val exchanged = mutableListOf<String>()
        var lowScore = 0
        var soldOut = 0
        val errors = mutableListOf<String>()

        for ((exchangeId, times) in EXCHANGE_PLAN) {
            val reward = rewards.firstOrNull { it.exchangeId == exchangeId } ?: continue
            var want = minOf(times, (reward.max - reward.exchanged).coerceAtLeast(0))
            if (want <= 0) {
                soldOut++
                continue
            }
            while (want > 0) {
                if (score < reward.score) {
                    lowScore++
                    break
                }
                try {
                    exchange(token, exchangeId)
                } catch (e: CommunityException) {
                    errors += "${reward.name}：${e.message}"
                    break
                }
                score -= reward.score
                exchanged += "${reward.name}×${reward.count}"
                want--
            }
        }

        val message = when {
            exchanged.isNotEmpty() -> buildString {
                append("已兑换 ${exchanged.size} 项：").append(exchanged.joinToString("、"))
                append("（消耗 ${scoreBefore - score} 分，剩余 $score 分）")
                if (lowScore > 0) append("；积分不足，还有 $lowScore 项没换")
                if (soldOut > 0) append("；另有 $soldOut 项本轮兑换次数已用完")
                if (errors.isNotEmpty()) append("；失败：").append(errors.joinToString("；"))
            }
            lowScore > 0 && errors.isEmpty() -> "积分不足：现有 $score 分，本轮没有可兑换的"
            soldOut > 0 && errors.isEmpty() -> "今天的兑换次数用完了，明天再来"
            errors.isNotEmpty() -> "兑换失败：" + errors.joinToString("；")
            else -> "没有可兑换的东西"
        }
        return CommunityStep("兑换", if (exchanged.isNotEmpty()) "ok" else if (errors.isEmpty()) "skip" else "error", message)
    }

    // ---------------------------------------------------------------- 帖子动作

    private fun topicList(token: CommunityToken): List<JSONObject> {
        val data = call(
            "GET", "/community/topic/list", token = token.token,
            query = "sort_type=1&category_id=1&query_type=1&last_tid=0&pub_time=0&reply_time=0" +
                "&hot_value=0&update_time=0&is_new_mark=0"
        )
        val array = data.optJSONArray("list") ?: return emptyList()
        return (0 until array.length()).mapNotNull { array.optJSONObject(it) }
    }

    private fun topicDetail(token: CommunityToken, tid: Long): JSONObject =
        call("GET", "/community/topic/$tid", token = token.token, query = "id=$tid")

    private fun topicLike(token: CommunityToken, tid: Long): JSONObject =
        call("GET", "/community/topic/like/$tid", token = token.token, query = "id=$tid")

    private fun topicShare(token: CommunityToken, tid: Long): JSONObject =
        call("GET", "/community/topic/share/$tid", token = token.token, query = "id=$tid")

    private fun exchange(token: CommunityToken, exchangeId: Int): JSONObject =
        call("POST", "/community/item/exchange", token = token.token, body = JSONObject().put("exchange_id", exchangeId))

    // ---------------------------------------------------------------- HTTP

    private fun call(
        method: String,
        path: String,
        token: String? = null,
        body: JSONObject? = null,
        query: String? = null
    ): JSONObject {
        val url = buildString {
            append(BASE).append(path)
            if (!query.isNullOrEmpty()) append('?').append(query)
        }
        val builder = Request.Builder().url(url).header("Accept", "application/json")
        if (!token.isNullOrEmpty()) builder.header("Authorization", token)
        when (method) {
            "GET" -> builder.get()
            "POST" -> builder.post((body ?: JSONObject()).toString().toRequestBody(JSON_TYPE))
            else -> throw CommunityException(0, "不支持的方法 $method")
        }

        val text = try {
            client.newCall(builder.build()).execute().use { response ->
                if (response.code == 401) throw CommunityException(401, "社区令牌已失效，请重新绑定")
                response.body?.string().orEmpty()
            }
        } catch (e: IOException) {
            throw CommunityException(0, "社区接口连接失败：${e.message ?: "网络异常"}")
        }

        val obj = try {
            JSONObject(text)
        } catch (e: Exception) {
            throw CommunityException(0, "社区接口返回异常")
        }
        val code = if (obj.has("Code")) obj.optInt("Code", -1) else obj.optInt("code", -1)
        if (code != 0) {
            val message = obj.optString("Message", obj.optString("message", "接口返回 $code"))
            throw CommunityException(code, message)
        }
        return obj.optJSONObject("data") ?: JSONObject()
    }
}
