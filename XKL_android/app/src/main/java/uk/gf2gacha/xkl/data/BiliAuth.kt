package uk.gf2gacha.xkl.data

import android.content.Context
import android.util.Base64
import com.base.crules.CustomRules
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.ensureActive
import kotlin.coroutines.coroutineContext
import okhttp3.FormBody
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import uk.gf2gacha.xkl.BuildConfig
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.spec.X509EncodedKeySpec
import java.util.UUID
import java.util.concurrent.TimeUnit
import javax.crypto.Cipher

/** B站短信 / 密码认证 -> 散爆游戏凭证。账号凭证不经过自建服务器。 */
object BiliAuth {
    private const val HOST = "line1-sdkcenter-login.bilibiligame.net"
    private const val APP_ID = "5279"
    private const val MERCHANT_ID = "1226"
    private const val SERVER_ID = "4424"
    private const val OTP_LOGIN = "/api/external/login/otp/v3"
    private const val PUBLIC_KEY = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCb0lFxD1OJX+sDvG1nn+QGi95wIRP71Y0r2js47NgTmYnMKKtwVbRdcpvc/MYeOQP1OUCUcQCBJaKWpTtsuIeFPgXYlIq7looKqxL5xzB2quEAinRVRTWaPpD5v0Re4n4b6SZmEr4BjVg2QhVrVE8gHWkFQlRZwf5f6TrrkdP+BQIDAQAB"
    private val excluded = setOf("item_name", "item_desc", "feign_sign", "token", "sign")
    private val random = SecureRandom()
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS).readTimeout(25, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false).build()
    private data class Rule(val value: String, val version: Int, val loadedAt: Long)
    @Volatile private var cachedRule: Rule? = null
    private val nativeLoaded: Unit by lazy {
        System.loadLibrary("crypto_1_1")
        System.loadLibrary("ssl_1_1")
        System.loadLibrary("custom_rules")
    }

    suspend fun sendSms(context: Context, phone: String): SmsChallenge = withContext(Dispatchers.IO) {
        val result = request(context, "/api/external/otp/send/v3", mapOf(
            "otp_type" to "login", "otp_channel_category" to "tel",
            "otp_channel_no" to phone, "country_code" to "86"
        ))
        val key = result.optString("captcha_key")
        if (key.isBlank()) throw Gf2Exception(-1, "B站未返回验证码凭证，请重新发送")
        SmsChallenge(phone, GameChannel.BILIBILI, key)
    }

    suspend fun login(context: Context, phone: String, code: String, challenge: SmsChallenge?): LoginResult =
        withContext(Dispatchers.IO) {
            if (challenge?.channel != GameChannel.BILIBILI || challenge.phone != phone || challenge.captchaKey.isBlank()) {
                throw Gf2Exception(-1, "请先为当前手机号发送B服验证码")
            }
            val account = request(context, OTP_LOGIN, mapOf(
                "mobile" to phone, "country_code" to "86",
                "captcha_key" to challenge.captchaKey, "otp" to code
            ))
            exchange(context, account)
        }

    suspend fun passwordLogin(
        context: Context,
        username: String,
        password: String,
        verify: suspend (BiliVerificationChallenge) -> BiliVerificationProof
    ): LoginResult = withContext(Dispatchers.IO) {
        val cipher = request(context, "/api/external/issue/cipher/v3", mapOf("cipher_type" to "bili_login_rsa"))
        val encrypted = encryptPassword(cipher.getString("hash"), password, cipher.getString("cipher_key"))
        val account = BiliPasswordFlow.authenticate(
            mapOf("user_id" to username, "pwd" to encrypted, "version" to "3"),
            attempt = { request(context, "/api/external/login/v3", it) },
            challenge = { code -> requestVerification(context, code) },
            verify = verify
        )
        coroutineContext.ensureActive()
        exchange(context, account)
    }

    internal fun encryptPassword(hash: String, password: String, pem: String): String {
        val encoded = pem.replace("-----BEGIN PUBLIC KEY-----", "").replace("-----END PUBLIC KEY-----", "")
        val key = KeyFactory.getInstance("RSA").generatePublic(X509EncodedKeySpec(Base64.decode(encoded, Base64.DEFAULT)))
        val cipher = Cipher.getInstance("RSA/ECB/PKCS1Padding")
        cipher.init(Cipher.ENCRYPT_MODE, key)
        return Base64.encodeToString(cipher.doFinal((hash + password).toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
    }

    private fun requestVerification(context: Context, code: Int): BiliVerificationChallenge {
        val json = if (code == 200006) request(context, "/api/external/start_captcha/v3",
            mapOf("captcha_category" to "acctAntiFraud", "version" to "3"))
        else request(context, "/api/client/start_captcha", mapOf("version" to "1"))
        val type = json.optString("captcha_type")
        return when (type) {
            "1" -> BiliVerificationChallenge(type, json.getString("gt_user_id"), json.getString("gt"),
                json.getString("challenge"), json.getString("gt_user_id"), json.optInt("gs", 1) != 0)
            "2" -> BiliVerificationChallenge(type, json.getString("image_token"), imageUrl = json.getString("url"))
            else -> throw Gf2Exception(-1, "暂不支持此次安全验证，请改用短信登录")
        }
    }

    private fun exchange(context: Context, account: JSONObject): LoginResult {
        val uid = account.optString("uid")
        val key = account.optString("access_key")
        if (uid.isBlank() || key.isBlank()) throw Gf2Exception(-1, "B站登录返回缺少账号凭证")
        val body = JSONObject().apply {
            put("uid", uid)
            put("access_key", key)
            put("game_name", "少女前线2：追放")
            put("game_channel_id", 6)
            put("device_num", device(context).first)
            put("mac", "")
            put("os", 1)
            put("language", "cn")
            put("reyun_channel_id", "bzaz")
        }
        val result = execute(Request.Builder().url("https://gf2-zoneinfo.sunborngame.com/bili/login")
            .post(body.toString().toRequestBody("application/json".toMediaType())).build())
        val data = result.optJSONObject("data") ?: throw Gf2Exception(-1, "游戏登录返回缺少数据")
        val gameUid = data.optString("uid")
        val token = data.optString("access_token")
        if (!gameUid.matches(Regex("[0-9]{4,32}")) || token.isBlank()) {
            throw Gf2Exception(-1, "游戏登录返回缺少 UID 或凭证")
        }
        return LoginResult(gameUid, token, data.optInt("is_guest") == 1)
    }


    /** 真机自测只读取配置并生成安全头，不发短信、不登录任何账号。 */
    suspend fun verifyConfiguration(context: Context): Boolean = withContext(Dispatchers.IO) {
        request(context, "/api/external/config/v3", emptyMap()).getInt("code") == 0
    }

    internal fun sign(parameters: Map<String, String>, appKey: String): String {
        val text = parameters.toSortedMap().filterKeys { it.lowercase() !in excluded }.values.joinToString("") + appKey
        return MessageDigest.getInstance("MD5").digest(text.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it.toInt() and 255) }
    }

    @Synchronized
    private fun device(context: Context): Pair<String, String> {
        val prefs = context.applicationContext.getSharedPreferences("bili_device", Context.MODE_PRIVATE)
        val udid = prefs.getString("udid", null) ?: ("X" + UUID.randomUUID()).also {
            prefs.edit().putString("udid", it).apply()
        }
        val bdid = prefs.getString("bdid", null) ?: ByteArray(32).also { random.nextBytes(it) }
            .joinToString("") { "%02x".format(it.toInt() and 255) }.also {
                prefs.edit().putString("bdid", it).apply()
            }
        return udid to bdid
    }

    private fun parameters(context: Context, business: Map<String, String>): MutableMap<String, String> {
        val (udid, bdid) = device(context)
        return linkedMapOf("app_id" to APP_ID, "game_id" to APP_ID, "merchant_id" to MERCHANT_ID,
            "server_id" to SERVER_ID, "channel_id" to "1", "platform" to "3", "platform_type" to "3",
            "sdk_type" to "1", "sdk_ver" to "5.9.0", "sdk_name" to "CGameSdk", "current_env" to "0",
            "version" to "3", "domain" to HOST, "apk_sign" to "4502a02a00395dec05a4134ad593224d",
            "udid" to udid, "cur_buvid" to udid, "old_buvid" to udid, "bd_id" to bdid
        ).apply { putAll(business); put("timestamp", System.currentTimeMillis().toString()) }
    }

    @Synchronized
    private fun rule(context: Context): Rule {
        cachedRule?.takeIf { System.currentTimeMillis() - it.loadedAt < 3_600_000 }?.let { return it }
        val params = parameters(context, emptyMap())
        params["sign"] = sign(params, BuildConfig.BILI_APP_KEY)
        val json = execute(formRequest("/api/external/config/v3", params))
        val value = json.optString("crule")
        if (value.isBlank()) throw Gf2Exception(-1, "暂时无法获取B服登录配置，请稍后重试")
        return Rule(value, json.optInt("crule_ver", 1), System.currentTimeMillis()).also { cachedRule = it }
    }

    private fun request(context: Context, path: String, business: Map<String, String>): JSONObject {
        if (BuildConfig.BILI_APP_KEY.isBlank()) throw Gf2Exception(-1, "当前安装包未配置B服登录")
        val rule = rule(context)
        val params = parameters(context, business)
        val signature = sign(params, BuildConfig.BILI_APP_KEY)
        val (udid, bdid) = device(context)
        val headers = try {
            nativeLoaded
            synchronized(CustomRules::class.java) { CustomRules(object : CustomRules.IProvider {
                override fun getRule() = rule.value
                override fun getVersion() = rule.version
                override fun getUdid() = udid
                override fun getCdid() = ""
                override fun getID() = SERVER_ID
                override fun getDeviceInfo() = "android"
            }).getTokens(hashMapOf("sign" to (BuildConfig.BILI_APP_KEY + signature),
                "importantKey" to params.getValue("timestamp"), "serviceID" to params.getValue("timestamp"),
                "gameID" to APP_ID, "bdid" to bdid)) }
        } catch (e: LinkageError) {
            throw Gf2Exception(-1, "这台设备暂不支持B服登录")
        }
        if (headers.isNullOrEmpty()) throw Gf2Exception(-1, "B服登录初始化失败，请稍后重试")
        params["sign"] = signature
        if (path == OTP_LOGIN) {
            val key = KeyFactory.getInstance("RSA").generatePublic(X509EncodedKeySpec(Base64.decode(PUBLIC_KEY, Base64.DEFAULT)))
            val cipher = Cipher.getInstance("RSA/ECB/PKCS1Padding")
            cipher.init(Cipher.ENCRYPT_MODE, key)
            params["feign_sign"] = Base64.encodeToString(cipher.doFinal(signature.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
        }
        val builder = formRequest(path, params).newBuilder()
        headers.forEach { (name, value) -> builder.header(name, value) }
        if (path == OTP_LOGIN) builder.header("x-nonce", (random.nextInt(900_000_000) + 100_000_000).toString())
        return execute(builder.build())
    }

    private fun formRequest(path: String, params: Map<String, String>): Request =
        Request.Builder().url("https://$HOST$path").post(FormBody.Builder().apply {
            params.forEach { (name, value) -> add(name, value) }
        }.build()).build()

    private fun execute(request: Request): JSONObject {
        val json = client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw Gf2Exception(response.code, "登录服务暂时不可用，请稍后重试")
            JSONObject(response.body?.string().orEmpty())
        }
        val code = json.optInt("code", -1)
        if (code != 0) {
            if (code in setOf(200000, 200001, 200005, 200006, 200007)) throw BiliVerificationRequired(code)
            val message = listOf("server_message", "msg", "message").map { json.optString(it) }.firstOrNull { it.isNotBlank() }
            throw Gf2Exception(code, message ?: "B服登录失败，请稍后重试")
        }
        return json
    }
}
