package uk.gf2gacha.xkl.data

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import uk.gf2gacha.xkl.BuildConfig
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * R2 公告中心。
 *
 * 远端布局（桶根目录）：
 *   announcements/manifest.json
 *   announcements/images/<图片文件名>
 *
 * 清单里图片写相对公告目录的路径即可，例如 "images/update.png"。
 */
object AnnouncementCenter {
    const val BASE_URL = "https://r2.gf2gacha-xkl.uk"

    private const val PREFS = "announcement_state"
    private const val KEY_LAST_SEEN = "last_seen_id"
    private const val KEY_CACHE_JSON = "manifest_cache_json"
    private const val KEY_CACHE_FETCHED_AT = "manifest_cache_fetched_at"
    private const val CACHE_TTL_SECONDS = 10L * 60L

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    data class Announcement(
        val id: String,
        val title: String,
        val body: String,
        val images: List<String>,
        val publishedAt: Long,
        val expiresAt: Long
    )

    data class Feed(
        val announcements: List<Announcement>,
        val updatedAt: Long
    )

    sealed class FetchResult {
        data class Success(
            val feed: Feed,
            val cached: Boolean = false,
            val stale: Boolean = false
        ) : FetchResult()
        data class Failed(val message: String) : FetchResult()
    }

    suspend fun fetch(context: Context, force: Boolean = false): FetchResult = withContext(Dispatchers.IO) {
        val preferences = prefs(context)
        val cachedText = preferences.getString(KEY_CACHE_JSON, null).orEmpty()
        val cachedAt = preferences.getLong(KEY_CACHE_FETCHED_AT, 0L)
        val now = System.currentTimeMillis() / 1000L
        val cacheFresh = cachedText.isNotBlank() && cachedAt > 0L && now - cachedAt in 0L..CACHE_TTL_SECONDS

        if (!force && cacheFresh) {
            try {
                return@withContext FetchResult.Success(parse(cachedText), cached = true)
            } catch (_: Exception) {
                preferences.edit().remove(KEY_CACHE_JSON).remove(KEY_CACHE_FETCHED_AT).apply()
            }
        }

        try {
            val request = Request.Builder()
                .url(BuildConfig.ANNOUNCEMENT_MANIFEST_URL)
                .header("Cache-Control", "no-cache")
                .build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) throw IOException("HTTP " + response.code)
                val text = response.body?.string().orEmpty()
                if (text.isBlank()) throw IOException("服务器返回空内容")
                val feed = parse(text)
                preferences.edit()
                    .putString(KEY_CACHE_JSON, text)
                    .putLong(KEY_CACHE_FETCHED_AT, now)
                    .apply()
                FetchResult.Success(feed)
            }
        } catch (e: Exception) {
            if (cachedText.isNotBlank()) {
                try {
                    return@withContext FetchResult.Success(parse(cachedText), cached = true, stale = true)
                } catch (_: Exception) {
                }
            }
            FetchResult.Failed(e.message ?: e.javaClass.simpleName)
        }
    }

    private fun parse(text: String): Feed {
        val root = JSONObject(text)
        val array = root.optJSONArray("announcements")
            ?: throw IOException("公告清单缺少 announcements 字段")
        val now = System.currentTimeMillis() / 1000L
        val items = ArrayList<Announcement>()
        for (i in 0 until array.length()) {
            val obj = array.optJSONObject(i) ?: continue
            if (!obj.optBoolean("active", true)) continue

            val id = obj.optString("id").trim()
            val title = obj.optString("title").trim()
            val body = obj.optString("body").trim()
            if (id.isEmpty() || title.isEmpty()) continue

            val expiresAt = obj.optLong("expires_at", 0L)
            if (expiresAt > 0L && expiresAt <= now) continue

            val images = ArrayList<String>()
            val imageArray = obj.optJSONArray("images")
            if (imageArray != null) {
                for (j in 0 until imageArray.length()) {
                    val image = imageArray.optString(j).trim()
                    if (image.isNotEmpty()) images.add(image)
                }
            }
            if (body.isEmpty() && images.isEmpty()) continue

            items.add(
                Announcement(
                    id = id,
                    title = title,
                    body = body,
                    images = images,
                    publishedAt = obj.optLong("published_at", 0L),
                    expiresAt = expiresAt
                )
            )
        }
        items.sortWith(compareByDescending<Announcement> { it.publishedAt }.thenByDescending { it.id })
        return Feed(items, root.optLong("updated_at", 0L))
    }

    fun mostRecent(feed: Feed): Announcement? = feed.announcements.firstOrNull()

    fun imageUrl(raw: String): String {
        val value = raw.trim()
        if (value.startsWith("https://") || value.startsWith("http://")) return value
        val path = value.trimStart('/')
        return if (path.startsWith("announcements/")) {
            BASE_URL + "/" + path
        } else {
            BASE_URL + "/announcements/" + path
        }
    }

    fun isUnread(context: Context, id: String): Boolean =
        prefs(context).getString(KEY_LAST_SEEN, null) != id

    fun markSeen(context: Context, id: String) {
        prefs(context).edit().putString(KEY_LAST_SEEN, id).apply()
    }

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
