package uk.gf2gacha.xkl.data

import android.content.Context
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * 五星表（item id -> 名字）。
 *
 * 数据源优先级：R2 远程表 -> 本机缓存 -> 内置 assets。
 * 之所以优先走 R2：出新角色/新武器时只要更新 R2 上的 ssr.json，**不用重新发版**。
 *
 * 表里有三份：SSR_character（人形）、SSR_weapon（武器）、SSR_permanent（常驻池五星）。
 * 「歪」的判定用的是 permanent —— 与 PC 版同一规则：抽到的五星属于常驻池即为歪。
 */
class SsrTable private constructor(
    val source: String,
    private val character: Map<Int, String>,
    private val weapon: Map<Int, String>,
    private val permanent: Map<Int, String>
) {
    private val characterMerged: Map<Int, String> = HashMap<Int, String>(permanent).apply { putAll(character) }
    private val weaponMerged: Map<Int, String> = HashMap<Int, String>(permanent).apply { putAll(weapon) }

    fun name(itemId: Int, poolType: Int): String? = mapFor(poolType)[itemId]

    /**
     * 该物品是不是武器。
     * 常驻池里人形和武器混在一起，光看池子判断不出来，必须按物品 id 判定：
     * 人形 id 是 4 位（1013~1085），武器 id 是 5 位（10133~11056）。
     */
    fun isWeaponItem(itemId: Int): Boolean {
        // 与 PC 版 isWeaponItem 逐字对齐：
        //   在限定武器表 -> 武器
        //   在限定人形表 -> 人形
        //   都没有（常驻池物品）-> 看 id 位数：5 位是武器，4 位是人形
        if (weapon.containsKey(itemId)) return true
        if (character.containsKey(itemId)) return false
        return itemId.toString().length == 5
    }

    /** 歪 = 该五星来自常驻池；常驻池自身没有"歪"的概念 */
    fun isWai(itemId: Int, poolType: Int): Boolean =
        poolType != Gf2Api.POOL_PERMANENT && permanent.containsKey(itemId)

    private fun mapFor(poolType: Int): Map<Int, String> = when (poolType) {
        Gf2Api.POOL_PERMANENT -> permanent
        Gf2Api.POOL_WEAPON, Gf2Api.POOL_CUSTOM_WEAPON -> weaponMerged
        else -> characterMerged
    }

    companion object {
        private const val REMOTE_URL = "https://r2.gf2gacha-xkl.uk/ssr.json"
        private const val CACHE_NAME = "ssr_cache.json"

        private val client: OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(6, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .build()

        @Volatile
        private var cached: SsrTable? = null

        /** 取当前表（不发网络）：内存 -> 本机缓存 -> 内置 assets */
        fun get(context: Context): SsrTable {
            cached?.let { return it }
            synchronized(this) {
                cached?.let { return it }
                val table = try {
                    val file = File(context.filesDir, CACHE_NAME)
                    if (file.isFile && file.length() > 100) {
                        parse(file.readText(), "本机缓存")
                    } else {
                        parse(readAsset(context), "内置")
                    }
                } catch (e: Exception) {
                    parse(readAsset(context), "内置")
                }
                cached = table
                return table
            }
        }

        /** 启动时调用：尝试用 R2 上的最新表替换，失败就静默保留旧表（不阻塞、不报错） */
        fun refresh(context: Context): SsrTable {
            val local = get(context)
            return try {
                val request = Request.Builder().url(REMOTE_URL).get().build()
                val body = client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return local
                    response.body?.string().orEmpty()
                }
                if (body.length < 100) return local
                val table = parse(body, "R2 远程")
                File(context.filesDir, CACHE_NAME).writeText(body)
                cached = table
                table
            } catch (e: Exception) {
                local
            }
        }

        private fun readAsset(context: Context): String =
            context.assets.open("ssr.json").bufferedReader(Charsets.UTF_8).use { it.readText() }

        private fun parse(text: String, source: String): SsrTable {
            val json = JSONObject(text)
            return SsrTable(
                source,
                readMap(json.optJSONObject("SSR_character")),
                readMap(json.optJSONObject("SSR_weapon")),
                readMap(json.optJSONObject("SSR_permanent"))
            )
        }

        private fun readMap(obj: JSONObject?): Map<Int, String> {
            val map = HashMap<Int, String>()
            if (obj != null) {
                val keys = obj.keys()
                while (keys.hasNext()) {
                    val key = keys.next()
                    val id = key.toIntOrNull()
                    if (id != null) map[id] = obj.optString(key)
                }
            }
            return map
        }
    }
}