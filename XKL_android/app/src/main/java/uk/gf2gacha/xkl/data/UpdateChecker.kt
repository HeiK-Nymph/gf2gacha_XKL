package uk.gf2gacha.xkl.data

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import uk.gf2gacha.xkl.BuildConfig
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

/**
 * 检查更新 / 下载新版本 APK。
 *
 * 约定与 PC 版（`updater.py` + `release/version.json`）**完全一致**，只是换个文件名：
 *
 *   检查文件  https://r2.gf2gacha-xkl.uk/version_android.json
 *   安装包    https://r2.gf2gacha-xkl.uk/gf2gacha_XKL_android.apk
 *
 * version_android.json 长这样（字段名和 PC 的一模一样）：
 * {
 *   "current_version": "0.1.1",
 *   "version_url":     "https://r2.gf2gacha-xkl.uk/version_android.json",
 *   "download_url":    "https://r2.gf2gacha-xkl.uk/gf2gacha_XKL_android.apk",
 *   "sha256":          "……",
 *   "size":            5285323,
 *   "update_info":     "这次改了什么"
 * }
 *
 * 流程（照 PC 那句「先校验再动手」）：
 *   1. 拉 json，按 PC 同款规则比版本号
 *   2. **用户点了「立即更新」才下载**
 *   3. 边下边算 sha256，和 json 里的 sha256 / size 对不上就直接删掉报错（防半包）
 *   4. 交给系统安装器 —— 签名不一致、版本降级都由系统拦，装不坏已装的版本
 */
object UpdateChecker {

    /** 发布包写死线上地址；调试包会指向 http://127.0.0.1:8000/…（真机自测更新链路用） */
    val VERSION_URL: String = BuildConfig.UPDATE_VERSION_URL

    /** json 里没给 download_url 时的兜底地址 */
    const val APK_URL = "https://r2.gf2gacha-xkl.uk/gf2gacha_XKL_android.apk"

    private const val APK_NAME = "gf2gacha_XKL_android.apk"

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    /** 远端声明的更新信息 */
    data class Update(
        val version: String,
        val downloadUrl: String,
        val sha256: String,
        val size: Long,
        val info: String
    )

    sealed class Result {
        /** 有新版 */
        data class Newer(val local: String, val update: Update) : Result()

        /** 已是最新 */
        data class Latest(val local: String, val remote: String) : Result()

        /** 检查失败：还没发布、网络不通、json 坏了…… 由调用方决定要不要提示 */
        data class Failed(val message: String) : Result()
    }

    // ------------------------------------------------------------------ 检查

    /** 本机版本号（就是 build.gradle.kts 里的 versionName） */
    fun localVersion(context: Context): String = try {
        context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: "0.0.0"
    } catch (e: Exception) {
        "0.0.0"
    }

    /** 与 PC `updater.py::_version_tuple` 同款：按 `.` 切开，每段只留数字，缺的按 0 算 */
    fun versionTuple(text: String?): List<Int> = (text ?: "").split(".").map { chunk ->
        val digits = chunk.filter { it.isDigit() }
        if (digits.isEmpty()) 0 else (digits.toIntOrNull() ?: 0)
    }

    fun isNewer(remote: String?, local: String?): Boolean {
        val a = versionTuple(remote)
        val b = versionTuple(local)
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }

    suspend fun check(context: Context): Result = withContext(Dispatchers.IO) {
        val local = localVersion(context)
        val json = try {
            val request = Request.Builder().url(VERSION_URL).build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) throw IOException("HTTP " + response.code)
                val text = response.body?.string().orEmpty()
                if (text.isBlank()) throw IOException("服务器返回空内容")
                JSONObject(text)
            }
        } catch (e: Exception) {
            return@withContext Result.Failed(describe(e))
        }

        val remote = json.optString("current_version")
        if (remote.isEmpty()) return@withContext Result.Failed("更新文件里没有 current_version 字段")
        if (!isNewer(remote, local)) return@withContext Result.Latest(local, remote)

        Result.Newer(
            local,
            Update(
                version = remote,
                downloadUrl = json.optString("download_url").ifEmpty { APK_URL },
                sha256 = json.optString("sha256"),
                size = json.optLong("size", 0L),
                info = json.optString("update_info")
            )
        )
    }

    private fun describe(e: Exception): String {
        val message = e.message ?: e.javaClass.simpleName
        return when {
            message.contains("HTTP 404") -> "还没有发布更新信息（HTTP 404）"
            message.contains("HTTP") -> "服务器返回 " + message
            else -> message
        }
    }

    // ------------------------------------------------------------------ 下载

    /**
     * 下载并校验；返回可以直接交给安装器的 APK 文件。
     *
     * 已经下好且校验通过的话直接复用（例如用户去过一次「允许安装未知应用」再回来点更新，
     * 不用重新下一遍 5MB）。
     */
    suspend fun download(context: Context, update: Update, onProgress: (Int) -> Unit): File =
        withContext(Dispatchers.IO) {
            val dir = File(context.cacheDir, "update")
            if (!dir.exists() && !dir.mkdirs()) throw IOException("无法创建下载目录")
            val dest = File(dir, APK_NAME)
            if (isValid(dest, update.sha256, update.size)) {
                onProgress(100)
                return@withContext dest
            }

            val part = File(dir, APK_NAME + ".part")
            if (part.exists()) part.delete()

            val request = Request.Builder().url(update.downloadUrl).build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) throw IOException("下载失败：HTTP " + response.code)
                val body = response.body ?: throw IOException("下载失败：响应为空")
                val total = if (update.size > 0) update.size else body.contentLength()
                val digest = MessageDigest.getInstance("SHA-256")
                var done = 0L
                var lastPercent = -1

                body.byteStream().use { input ->
                    FileOutputStream(part).use { output ->
                        val buffer = ByteArray(64 * 1024)
                        while (true) {
                            currentCoroutineContext().ensureActive()   // 用户点「取消」立刻退出
                            val n = input.read(buffer)
                            if (n < 0) break
                            if (n == 0) continue
                            output.write(buffer, 0, n)
                            digest.update(buffer, 0, n)
                            done += n
                            if (total > 0) {
                                val percent = ((done * 100) / total).toInt().coerceIn(0, 100)
                                if (percent != lastPercent) {
                                    lastPercent = percent
                                    onProgress(percent)
                                }
                            }
                        }
                    }
                }

                val actual = digest.digest().joinToString("") { "%02x".format(it) }
                if (update.sha256.isNotEmpty() && !actual.equals(update.sha256, ignoreCase = true)) {
                    part.delete()
                    throw IOException("完整性校验没通过（sha256 不一致），文件可能没传完，稍后再试")
                }
                if (update.size > 0 && done != update.size) {
                    part.delete()
                    throw IOException("完整性校验没通过（大小 " + done + " / " + update.size + "）")
                }

                if (dest.exists()) dest.delete()
                if (!part.renameTo(dest)) {
                    part.copyTo(dest, overwrite = true)
                    part.delete()
                }
                onProgress(100)
                dest
            }
        }

    private fun isValid(file: File, sha256: String, size: Long): Boolean {
        if (!file.isFile) return false
        if (size > 0 && file.length() != size) return false
        if (sha256.isEmpty()) return file.length() > 0
        return sha256Of(file).equals(sha256, ignoreCase = true)
    }

    private fun sha256Of(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(256 * 1024)
            while (true) {
                val n = input.read(buffer)
                if (n < 0) break
                digest.update(buffer, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    // ------------------------------------------------------------------ 安装

    /** 系统是否还没允许本应用「安装未知应用」（Android 8+ 才有这个限制） */
    fun needInstallPermission(context: Context): Boolean =
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
            !context.packageManager.canRequestPackageInstalls()

    /** 跳到「安装未知应用」开关页，让用户给本应用放行 */
    fun openInstallPermissionSettings(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val intent = Intent(
            Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
            Uri.parse("package:" + context.packageName)
        ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            context.startActivity(intent)
        } catch (e: Exception) {
            try {
                context.startActivity(
                    Intent(Settings.ACTION_SECURITY_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                )
            } catch (e2: Exception) {
            }
        }
    }

    /** 拉起系统安装器（同一份 APK 覆盖安装，签名不对会被系统拒绝） */
    fun install(context: Context, apk: File) {
        val uri = FileProvider.getUriForFile(context, context.packageName + ".files", apk)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }
}
