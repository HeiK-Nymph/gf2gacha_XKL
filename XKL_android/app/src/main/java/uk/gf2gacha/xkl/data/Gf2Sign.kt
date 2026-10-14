package uk.gf2gacha.xkl.data

import android.content.Context
import android.provider.Settings
import java.security.MessageDigest
import java.util.UUID

/**
 * 签名与设备号。
 *
 * 规则来自官方客户端 Java 层 com.mica.baselib.utils.MD5U：
 *     sign = md5("device_num=X&phone_number=Y&timestamp=T")
 * 参与签名的 key 按字典序排序、用 & 连接，**没有密钥**。
 * 该算法已用官方客户端真实报文逐字节验算通过。
 */
object Gf2Sign {

    private const val KEY_DEVICE_NUM = "device_num"
    private val HEX = "0123456789abcdef".toCharArray()

    /** 与客户端 MD5U.encrypt 完全一致：32 位小写 hex */
    fun md5(input: String): String {
        val digest = MessageDigest.getInstance("MD5").digest(input.toByteArray(Charsets.UTF_8))
        val out = CharArray(digest.size * 2)
        for (i in digest.indices) {
            val v = digest[i].toInt() and 0xFF
            out[i * 2] = HEX[v ushr 4]
            out[i * 2 + 1] = HEX[v and 0x0F]
        }
        return String(out)
    }

    fun sign(deviceNum: String, phone: String, timestamp: Long): String =
        md5("device_num=$deviceNum&phone_number=$phone&timestamp=$timestamp")

    /**
     * 设备号，与官方 NetU.getAppUUID 一致：由 ANDROID_ID 派生一次并本地持久化。
     * 注意：每台设备必须固定一个，不能每次随机。
     */
    fun deviceNum(context: Context): String {
        val sp = context.getSharedPreferences("gf2_device", Context.MODE_PRIVATE)
        val saved = sp.getString(KEY_DEVICE_NUM, null)
        if (!saved.isNullOrEmpty()) return saved

        val androidId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
        val value = if (!androidId.isNullOrEmpty()) {
            UUID.nameUUIDFromBytes(androidId.toByteArray(Charsets.UTF_8)).toString()
        } else {
            UUID.randomUUID().toString()
        }
        sp.edit().putString(KEY_DEVICE_NUM, value).apply()
        return value
    }
}