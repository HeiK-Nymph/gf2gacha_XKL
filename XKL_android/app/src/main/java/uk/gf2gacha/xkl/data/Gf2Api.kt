package uk.gf2gacha.xkl.data

import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import okhttp3.FormBody
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONException
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/** 接口返回 code != 0 或网络异常 */
class Gf2Exception(val code: Int, message: String) : Exception(message) {
    /** 令牌失效（同账号在别处重新登录会让旧令牌作废） */
    val isTokenError: Boolean get() = code == 401 ||
        message?.contains("token", ignoreCase = true) == true ||
        Regex("(登录|凭证).*(过期|失效)").containsMatchIn(message.orEmpty())
}

data class GachaRecord(val poolId: Int, val itemId: Int, val time: Long, val itemNum: Int)

data class SsrHit(
    val time: Long,
    val itemId: Int,
    val name: String,
    val costDraws: Int,
    val isWai: Boolean = false
)

data class PoolResult(
    val poolType: Int,
    val poolName: String,
    val isWeapon: Boolean,
    val records: List<GachaRecord>,
    val ssrHits: List<SsrHit>,
    val pity: Int
) {
    val total: Int get() = records.size
    val ssrCount: Int get() = ssrHits.size
    /** 平均多少抽出金；没出过金返回 0 */
    val average: Int get() = if (ssrCount == 0) 0 else Math.round(total.toFloat() / ssrCount)
    val maxCost: Int get() = ssrHits.maxOfOrNull { it.costDraws } ?: 0
    /** 歪的个数（常驻池恒为 0） */
    val waiCount: Int get() = ssrHits.count { it.isWai }
}

data class LoginResult(
    val uid: String,
    val accessToken: String,
    val isGuest: Boolean,
    /** 服务端返回的绑定手机号；**邮箱登录时为 null**，所以邮箱账号不能用短信续登 */
    val phoneNumber: String? = null
)

/**
 * 官方接口封装。协议见 ../GF2_SMS_LOGIN_PROTOCOL.md
 *
 * 性能要点（实测 12.1s -> 2.5s，快 4.8 倍）：
 *   1. 记录接口支持 limit 参数，实测上限 20（默认只有 6）-> 请求数少 3.33 倍
 *   2. 五个池子互相独立，用并发一起拉（池内靠 next 游标串行，无法并行）
 */
object Gf2Api {

    data class Pool(val typeId: Int, val name: String, val isWeapon: Boolean)

    /**
     * 卡池顺序**必须与 PC 版一致**（PC 的 sharePoolOptions / 主界面都是这个从左到右顺序）：
     * 角色池 / 武器池 / 常驻池 / 自选角色池 / 自选武器池
     */
    val POOLS: List<Pool> = listOf(
        Pool(3, "角色池", false),
        Pool(4, "武器池", true),
        Pool(1, "常驻池", false),
        Pool(6, "自选角色池", false),
        Pool(7, "自选武器池", true)
    )

    /**
     * 角色头像 CDN。与 `r2.gf2gacha-xkl.uk` 指向**同一个 R2 桶**（实测同一张图 ETag 相同），
     * 也是 PC 版 `getImagePath` 用的地址 —— 所以新角色图一上传到 R2，App 不用更新就能显示。
     * 武器图使用同一图床的 /images/weapon/ 目录，命名规则与微信小程序端一致。
     */
    const val IMAGE_BASE = "https://static.gf2gacha-xkl.uk/images/character/"
    const val WEAPON_IMAGE_BASE = "https://static.gf2gacha-xkl.uk/images/weapon/"

    const val POOL_PERMANENT = 1
    const val POOL_CHARACTER = 3
    const val POOL_WEAPON = 4
    const val POOL_CUSTOM_CHARACTER = 6
    const val POOL_CUSTOM_WEAPON = 7

    private const val SMS_URL = "https://gf2-cn-plateuser.sunborngame.com/sms/phone_login"
    private const val LOGIN_URL = "https://gf2-zoneinfo.sunborngame.com/phone/sms_login"

    /**
     * 账号密码登录（官方 com.mica.micasdk.repository.http.ApiMethod.PHONE_LOGIN = "phone/login"）。
     * 和短信登录**同一个 host**，但 body 里不带 sign / timestamp。
     */
    private const val PWD_LOGIN_URL = "https://gf2-zoneinfo.sunborngame.com/phone/login"

    /**
     * 邮箱账号密码登录（官方 `com.mica.micasdk.repository.http.ApiMethod.EMAIL_LOGIN = "email/login"`）。
     * 与 [PWD_LOGIN_URL] 同一个 host、同一套公共参数，**同样不带 sign / timestamp**。
     * 2026-10-28 用官方 PC 客户端抓包逐字段核对过。
     */
    private const val EMAIL_LOGIN_URL = "https://gf2-zoneinfo.sunborngame.com/email/login"
    private const val LIST_URL = "https://gf2-gacha-record.sunborngame.com/list"
    private const val ACCOUNT_INFO_URL = "https://gf2-zoneinfo.sunborngame.com/account/info"

    private const val USER_AGENT = "UnityPlayer/2019.4.40f1 (UnityWebRequest/1.0, libcurl/7.80.0-DEV)"
    private const val UNITY_VERSION = "2019.4.40f1"
    private const val MAX_PAGES = 600
    private const val TAG = "XKL"
    private const val PAGE_SIZE = 20

    private val JSON_TYPE = "application/json".toMediaType()

    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    // ------------------------------------------------------------------ 登录

    /**
     * 向账号接口要凭证对应的 UID（用于导出前确认钥匙里的 UID 没被改错）。
     *
     * **不能拿它当过期检查**：账号接口只校验签名，access_token 过期后照样返回 uid。
     * 判断凭证是否可用要用 [verifyCredential]（与刷新同一条记录接口）。
     */
    suspend fun fetchAccountUid(token: String, channel: GameChannel = GameChannel.OFFICIAL): String = withContext(Dispatchers.IO) {
        val url = ACCOUNT_INFO_URL.toHttpUrlOrNull()?.newBuilder()
            ?.addQueryParameter("game_channel_id", channel.id.toString())
            ?.addQueryParameter("type_id", "3")
            ?.build()
            ?: throw Gf2Exception(-1, "账号接口地址不合法")
        val request = Request.Builder()
            .url(url)
            .post("{}".toRequestBody(JSON_TYPE))
            .header("User-Agent", USER_AGENT)
            .header("X-Unity-Version", UNITY_VERSION)
            .header("Authorization", token)
            .build()
        val json = execute(request)
        checkOk(json)
        val uid = json.optJSONObject("data")?.optString("uid", "").orEmpty()
        if (!uid.matches(Regex("[0-9]{4,32}"))) throw Gf2Exception(-1, "官方返回的 UID 不合法")
        uid
    }

    /**
     * 按「刷新」同一条链路核验凭证是否**真的**还能用。
     *
     * 刷新是先打记录接口，`token err` 时走续登；导出也必须用这个判据 —— 账号接口
     * （[fetchAccountUid]）对过期凭证仍返回 uid，只看它会导出一把用不了的钥匙。
     * 这里只取记录接口第一页（不翻页、不合并、不落盘），凭证失效会在 [checkOk] 抛
     * [Gf2Exception]，[Gf2Exception.isTokenError] 为 true。
     */
    suspend fun verifyCredential(token: String, channel: GameChannel = GameChannel.OFFICIAL) {
        withContext(Dispatchers.IO) {
            checkOk(listPage(token, POOL_CHARACTER, null, channel))
        }
    }

    suspend fun sendSmsCode(context: Context, phone: String, channel: GameChannel = GameChannel.OFFICIAL): SmsChallenge = withContext(Dispatchers.IO) {
        if (channel == GameChannel.BILIBILI) return@withContext BiliAuth.sendSms(context, phone)
        val deviceNum = Gf2Sign.deviceNum(context)
        val timestamp = System.currentTimeMillis() / 1000
        val body = commonBody(deviceNum, phone, timestamp)
        body.put("x", -1)
        checkOk(postJson(SMS_URL, body))
        SmsChallenge(phone, channel)
    }

    suspend fun smsLogin(context: Context, phone: String, verifyCode: String,
                         channel: GameChannel = GameChannel.OFFICIAL, challenge: SmsChallenge? = null): LoginResult =
        withContext(Dispatchers.IO) {
            if (channel == GameChannel.BILIBILI) return@withContext BiliAuth.login(context, phone, verifyCode, challenge)
            val deviceNum = Gf2Sign.deviceNum(context)
            val timestamp = System.currentTimeMillis() / 1000
            val body = commonBody(deviceNum, phone, timestamp)
            body.put("verify_code", verifyCode)
            val json = postJson(LOGIN_URL, body)
            checkOk(json)
            parseLogin(json)
        }

    /**
     * 手机号 + 密码登录。
     *
     * 逆向自官方 MicaSDK（`LoginP.phoneLogin` → `MD5U.encrypt` → `ApiClientAccount.phoneLogin`）：
     *
     *   1. 密码提交的是 **`md5(明文密码)` 的 32 位小写 hex**（`MD5U.encrypt`，无盐、无密钥）
     *   2. 请求体**只有公共参数 + phone_number / area_code / passwd** —— 和短信登录不同，
     *      **不加 `sign`、不加 `timestamp`**（`phoneLogin` 没调 `simpleSign`）
     *   3. 返回结构和 `phone/sms_login` 完全一致
     *
     * 明文密码只在本方法内存里活一次：算完 MD5 就丢掉，不写日志、不落盘。
     */
    suspend fun passwordLogin(context: Context, phone: String, password: String): LoginResult =
        withContext(Dispatchers.IO) {
            require(password.isNotEmpty()) { "密码不能为空" }
            val deviceNum = Gf2Sign.deviceNum(context)
            val body = loginBody(deviceNum).apply {
                put("area_code", "+86")
                put("phone_number", phone)
                put("passwd", Gf2Sign.md5(password))   // 官方就是裸 MD5
            }
            val json = postJson(PWD_LOGIN_URL, body)
            checkOk(json)
            parseLogin(json)
        }

    /**
     * 邮箱 + 密码登录（官服）。
     *
     * 与 [passwordLogin] 同源（官方 `LoginP.emailLogin` → `ApiClientAccount.emailLogin`），
     * 差别只有三处：
     *   1. 账号字段是 `email`，不是 `phone_number`
     *   2. **不带 `area_code`**（官方 `emailLogin` 只往 body 加 email / passwd）
     *   3. 返回的 data 里没有 `phone_number`，所以邮箱账号**不能用短信续登**
     *
     * 2026-10-28 用 PC 客户端真实登录抓包核对：报文逐字段一致，响应 `code=0`。
     * 明文密码同样只在内存里活一次。
     */
    suspend fun emailLogin(context: Context, email: String, password: String): LoginResult =
        withContext(Dispatchers.IO) {
            require(password.isNotEmpty()) { "密码不能为空" }
            val deviceNum = Gf2Sign.deviceNum(context)
            val body = loginBody(deviceNum).apply {
                put("email", email)
                put("passwd", Gf2Sign.md5(password))
            }
            val json = postJson(EMAIL_LOGIN_URL, body)
            checkOk(json)
            parseLogin(json)
        }

    /** 两种密码登录共用的公共参数（不含 area_code 与账号字段） */
    private fun loginBody(deviceNum: String): JSONObject = JSONObject().apply {
        // 与短信登录同源，取自官方 ApiCommon.addCommonParams
        put("os", 3)
        put("reyun_channel_id", "1029")
        put("game_channel_id", 5)
        put("device_num", deviceNum)
        put("language", "cn")
        put("mac", "")
    }

    /** 三种登录（短信 / 手机号密码 / 邮箱密码）的返回结构一致，解析共用 */
    private fun parseLogin(json: JSONObject): LoginResult {
        val data = json.optJSONObject("data")
            ?: throw Gf2Exception(-1, "登录返回缺少 data 字段")
        val token = data.optString("access_token", "")
        if (token.isEmpty()) throw Gf2Exception(-1, "登录返回缺少 access_token")
        // 短信/手机号密码会带 phone_number；邮箱登录实测没有这个字段
        val phone = data.optString("phone_number", "").takeIf { it.isNotEmpty() }
        return LoginResult(
            uid = data.optString("uid", ""),
            accessToken = token,
            isGuest = data.optInt("is_guest", 0) == 1,
            phoneNumber = phone
        )
    }

    private fun commonBody(deviceNum: String, phone: String, timestamp: Long): JSONObject {
        val sign = Gf2Sign.sign(deviceNum, phone, timestamp)
        return JSONObject().apply {
            put("os", 3)
            put("reyun_channel_id", "1029")
            put("game_channel_id", 5)
            put("device_num", deviceNum)
            put("timestamp", timestamp)
            put("language", "cn")
            put("area_code", "+86")
            put("sign", sign)
            put("phone_number", phone)
            put("mac", "")
        }
    }

    // ------------------------------------------------------------ 抽卡记录

    /**
     * 并发拉取全部五个池子。每完成一个池子就回调一次（UI 可以逐池渲染，不必等全部完成）。
     * 回调在主线程执行。
     */
    suspend fun fetchAllPools(
        context: Context,
        token: String,
        known: Map<Int, List<GachaRecord>> = emptyMap(),
        channel: GameChannel = GameChannel.OFFICIAL,
        onPool: (PoolResult) -> Unit
    ): List<PoolResult> = coroutineScope {
        // 先快照一份：回调里 store 会改原 map，不能边改边被别的池子读到
        val knownSnapshot = HashMap(known)
        POOLS.map { pool ->
            async(Dispatchers.IO) {
                val result = fetchPool(context, token, pool, knownSnapshot[pool.typeId].orEmpty(), channel)
                withContext(Dispatchers.Main) { onPool(result) }
                result
            }
        }.awaitAll()
    }

    /**
     * 拉单个池子。**全量翻页，一页都不许少**：
     * 接口按「最新在前」返回，`next` 是 `时间-id` 复合游标、伪造无效，只能从第 1 页一路翻到
     * `next` 为空为止 —— 少翻一页就可能漏记录，所以这里不做「看着都存过了就提前停」的优化。
     *
     * 「增量」发生在**合并**这一步（对齐 PC 版 `main.py::_merge_pool_data`）：
     * 全量拉回来的记录不覆盖本地，而是与 [known] 按 fakeId 去重合并 ——
     * 官方记录接口只保留一段时间的记录，窗口一往前滑，覆盖写就会把本地更早的历史弄丢。
     */
    suspend fun fetchPool(
        context: Context,
        token: String,
        pool: Pool,
        known: List<GachaRecord> = emptyList(),
        channel: GameChannel = GameChannel.OFFICIAL
    ): PoolResult =
        withContext(Dispatchers.IO) {
            val startedAt = System.currentTimeMillis()
            val raw = ArrayList<GachaRecord>()
            var next: String? = null
            var page = 0
            while (true) {
                page++
                if (page > MAX_PAGES) throw Gf2Exception(-1, "翻页超过 $MAX_PAGES 页，疑似接口异常")
                val json = listPage(token, pool.typeId, next, channel)
                checkOk(json)
                val data = json.optJSONObject("data")
                var nextCursor: String? = null
                if (data != null) {
                    val list = data.optJSONArray("list")
                    if (list != null) {
                        for (i in 0 until list.length()) {
                            val item = list.optJSONObject(i) ?: continue
                            raw.add(
                                GachaRecord(
                                    poolId = item.optInt("pool_id"),
                                    itemId = item.optInt("item"),
                                    time = item.optLong("time"),
                                    itemNum = item.optInt("item_num", 1)
                                )
                            )
                        }
                    }
                    val cursor = data.optString("next", "")
                    if (cursor.isNotEmpty()) nextCursor = cursor
                }
                if (nextCursor == null) break
                next = nextCursor
            }

            val merged = RecordMerge.merge(raw, known)
            Log.i(
                TAG,
                pool.name + "：" + page + " 页 / 拉到 " + raw.size + " 条 / 新增 " +
                    (merged.size - known.size) + " 条 / 合计 " + merged.size + " 条 / " +
                    (System.currentTimeMillis() - startedAt) + "ms"
            )
            analyze(context, pool, merged)
        }

    private fun listPage(token: String, poolType: Int, next: String?, channel: GameChannel): JSONObject {
        val base = LIST_URL.toHttpUrlOrNull() ?: throw Gf2Exception(-1, "记录接口地址不合法")
        val url = base.newBuilder()
            .addQueryParameter("game_channel_id", channel.id.toString())
            .addQueryParameter("type_id", "3")
            .build()

        val form = FormBody.Builder()
            .add("type_id", poolType.toString())
            .add("limit", PAGE_SIZE.toString())
        if (!next.isNullOrEmpty()) form.add("next", next)

        val request = Request.Builder()
            .url(url)
            .post(form.build())
            .header("User-Agent", USER_AGENT)
            .header("X-Unity-Version", UNITY_VERSION)
            .header("Authorization", token)
            .build()
        return execute(request)
    }

    /** 用本地缓存的原始记录离线重算统计（切换账号/无网络时用，不发请求） */
    fun analyzeCached(context: Context, pool: Pool, raw: List<GachaRecord>): PoolResult =
        analyze(context, pool, raw)

    /** 统计：每条五星花了多少抽、当前垫抽数（records 已按时间升序） */
    private fun analyze(context: Context, pool: Pool, raw: List<GachaRecord>): PoolResult {
        val table = SsrTable.get(context)
        val sorted = raw.sortedBy { it.time }
        val hits = ArrayList<SsrHit>()
        var pity = 0
        for (record in sorted) {
            pity++
            val name = table.name(record.itemId, pool.typeId)
            if (name != null) {
                hits.add(
                    SsrHit(
                        time = record.time,
                        itemId = record.itemId,
                        name = name,
                        costDraws = pity,
                        isWai = table.isWai(record.itemId, pool.typeId)
                    )
                )
                pity = 0
            }
        }
        return PoolResult(pool.typeId, pool.name, pool.isWeapon, sorted, hits, pity)
    }

    // ---------------------------------------------------------------- 底层

    private fun postJson(url: String, body: JSONObject): JSONObject {
        val request = Request.Builder()
            .url(url)
            .post(body.toString().toRequestBody(JSON_TYPE))
            .header("User-Agent", USER_AGENT)
            .header("X-Unity-Version", UNITY_VERSION)
            .header("Accept", "*/*")
            .build()
        return execute(request)
    }

    private fun execute(request: Request): JSONObject {
        val response: Response = client.newCall(request).execute()
        val text: String = response.use { it.body?.string().orEmpty() }
        if (!response.isSuccessful) {
            throw Gf2Exception(response.code, "HTTP ${response.code}：${text.take(160)}")
        }
        if (text.isEmpty()) throw Gf2Exception(-1, "服务器返回空内容")
        return try {
            JSONObject(text)
        } catch (e: JSONException) {
            throw Gf2Exception(-1, "返回内容不是 JSON：${text.take(160)}")
        }
    }

    private fun checkOk(json: JSONObject) {
        val code = json.optInt("code", -1)
        if (code != 0) {
            var msg = json.optString("msg", "")
            if (msg.isEmpty()) msg = json.optString("message", "")
            if (msg.isEmpty()) msg = "接口返回 code=$code"
            throw Gf2Exception(code, msg)
        }
    }
}
