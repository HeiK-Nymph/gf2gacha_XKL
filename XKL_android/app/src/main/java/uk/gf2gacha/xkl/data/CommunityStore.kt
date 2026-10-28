package uk.gf2gacha.xkl.data

import android.content.Context
import org.json.JSONObject
import java.io.File

/**
 * 社区令牌本地存储（files/community.json）。
 *
 * 按账号 key 存（官服=uid、B服=bili:uid），和 AccountStore 的多账号模型一致：
 * 切号时各自用各自的社区 JWT，不用重新绑定。
 * 令牌是 30 天有效的凭据，只存本机、不上传。
 */
class CommunityStore(context: Context) {

    private val file = File(context.filesDir, "community.json")
    private val items = LinkedHashMap<String, CommunityToken>()

    init {
        reload()
    }

    private fun reload() {
        items.clear()
        if (!file.isFile) return
        try {
            val root = JSONObject(file.readText())
            val accounts = root.optJSONObject("accounts") ?: return
            val keys = accounts.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                val obj = accounts.optJSONObject(key) ?: continue
                val token = obj.optString("token")
                if (token.isEmpty()) continue
                items[key] = CommunityToken(
                    token = token,
                    uid = obj.optLong("uid", 0L),
                    platformId = obj.optLong("platformId", 0L),
                    exp = obj.optLong("exp", 0L)
                )
            }
        } catch (e: Exception) {
            // 文件损坏就先当空，交给下次绑定重写
        }
    }

    fun get(accountKey: String): CommunityToken? = items[accountKey]

    fun put(accountKey: String, token: CommunityToken) {
        items[accountKey] = token
        save()
    }

    fun remove(accountKey: String) {
        items.remove(accountKey)
        save()
    }

    private fun save() {
        val accounts = JSONObject()
        for ((key, token) in items) {
            accounts.put(
                key,
                JSONObject().apply {
                    put("token", token.token)
                    put("uid", token.uid)
                    put("platformId", token.platformId)
                    put("exp", token.exp)
                }
            )
        }
        try {
            file.writeText(JSONObject().put("accounts", accounts).toString())
        } catch (e: Exception) {
            // 写失败不致命：下次刷新会重新绑定
        }
    }
}
