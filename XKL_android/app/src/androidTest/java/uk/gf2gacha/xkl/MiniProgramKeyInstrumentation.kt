package uk.gf2gacha.xkl

import android.app.Activity
import android.app.Instrumentation
import android.content.ClipboardManager
import android.content.Context
import android.content.ContextWrapper
import android.content.ClipDescription
import android.os.Bundle
import android.util.Base64
import org.json.JSONObject
import uk.gf2gacha.xkl.data.MiniProgramKey
import uk.gf2gacha.xkl.data.AccountStore
import uk.gf2gacha.xkl.data.GachaRecord
import uk.gf2gacha.xkl.data.Gf2Exception
import uk.gf2gacha.xkl.ui.MainActivity
import java.io.File

/** 直接在 Android 运行时验证与小程序协议兼容，不读取真实账号或剪贴板。 */
class MiniProgramKeyInstrumentation : Instrumentation() {
    private var verifyClipboard = false
    private var verifyReauth = false
    private lateinit var isolatedStore: AccountStore
    private lateinit var isolatedDir: File

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        verifyClipboard = arguments?.getString("verifyClipboard") == "true"
        verifyReauth = arguments?.getString("verifyReauth") == "true"
        if (verifyReauth) {
            isolatedDir = File(targetContext.cacheDir, "reauth-test-${System.nanoTime()}").apply { mkdirs() }
            isolatedStore = AccountStore(object : ContextWrapper(targetContext) {
                override fun getFilesDir(): File = isolatedDir
            })
        }
        start()
    }

    override fun callActivityOnCreate(activity: Activity, icicle: Bundle?) {
        super.callActivityOnCreate(activity, icicle)
        if (verifyReauth && activity is MainActivity) {
            // 在首次 onResume 之前替换，绝不读写真实账号文件或查询真实账号。
            MainActivity::class.java.getDeclaredField("store").apply { isAccessible = true }
                .set(activity, isolatedStore)
        }
    }

    override fun onStart() {
        if (verifyReauth) {
            verifyReauthPrompts()
            return
        }
        if (verifyClipboard) {
            verifyExportedClipboard()
            return
        }
        var passed = 0
        val failures = mutableListOf<String>()
        fun verify(name: String, body: () -> Unit) {
            try {
                body()
                passed++
            } catch (e: Exception) {
                // 不回显异常内容，避免失败信息包含正在测试的凭证。
                failures.add(name)
            }
        }
        fun rejects(body: () -> Unit) {
            try { body() } catch (e: IllegalArgumentException) { return }
            error("应拒绝非法输入")
        }

        verify("与小程序协议示例逐字一致") {
            check(MiniProgramKey.encode("123456789", "demo") ==
                "XKL1.eyJ2ZXJzaW9uIjoxLCJ1aWQiOiIxMjM0NTY3ODkiLCJjcmVkZW50aWFsIjoiZGVtbyJ9")
        }
        verify("UTF-8 往返且仅包含三项协议字段") {
            val credential = "测试凭证+/=."
            val key = MiniProgramKey.encode("123456789", credential)
            check(key.matches(Regex("XKL1\\.[A-Za-z0-9_-]+")))
            val json = JSONObject(String(Base64.decode(key.substring(5), Base64.URL_SAFE), Charsets.UTF_8))
            check(json.length() == 3 && json.getInt("version") == 1)
            check(json.getString("uid") == "123456789" && json.getString("credential") == credential)
        }
        verify("拒绝错误 UID") {
            listOf("", "123", "a1234", "1".repeat(33)).forEach { uid -> rejects { MiniProgramKey.encode(uid, "demo") } }
        }
        verify("拒绝空凭证与换行注入") {
            listOf("", "  ", "demo\r\ninjected", "demo\n").forEach { token -> rejects { MiniProgramKey.encode("123456789", token) } }
        }
        verify("凭证长度边界") {
            MiniProgramKey.encode("123456789", "a".repeat(4096))
            rejects { MiniProgramKey.encode("123456789", "a".repeat(4097)) }
        }
        verify("剪贴板标记为敏感内容") {
            val key = MiniProgramKey.encode("123456789", "demo")
            val clip = MiniProgramKey.clip(key)
            check(clip.itemCount == 1 && clip.getItemAt(0).text.toString() == key)
            check(clip.description.extras?.getBoolean(ClipDescription.EXTRA_IS_SENSITIVE) == true)
            check(clip.description.label == "小程序导入钥匙")
        }
        verify("凭证过期识别且不误判普通网络错误") {
            listOf(Gf2Exception(401, "Unauthorized"), Gf2Exception(1, "token expired"),
                Gf2Exception(1, "登录已过期"), Gf2Exception(1, "凭证失效")).forEach { check(it.isTokenError) }
            check(!Gf2Exception(500, "服务器异常").isTokenError)
            check(!Gf2Exception(-1, "网络连接超时").isTokenError)
        }
        val result = Bundle().apply {
            putInt("passed", passed)
            putInt("failed", failures.size)
            putString("stream", "钥匙协议测试：通过 $passed，失败 ${failures.size}" +
                if (failures.isEmpty()) "" else "；" + failures.joinToString("、"))
        }
        finish(if (failures.isEmpty()) Activity.RESULT_OK else Activity.RESULT_CANCELED, result)
    }

    /** 只点取消，覆盖刷新/导出的无账号和过期分支；不调用短信接口。 */
    private fun verifyReauthPrompts() {
        var activity: Activity? = null
        var passed = 0
        val failures = mutableListOf<String>()
        try {
            val monitor = addMonitor(MainActivity::class.java.name, null, false)
            activity = try {
                android.os.ParcelFileDescriptor.AutoCloseInputStream(uiAutomation.executeShellCommand(
                    "am start -n ${targetContext.packageName}/${MainActivity::class.java.name}"
                )).use { it.readBytes() }
                waitForMonitorWithTimeout(monitor, 5000) ?: error("主界面启动超时")
            } finally { removeMonitor(monitor) }
            val screen = activity as MainActivity
            runOnMainSync {
                for (scenario in listOf("无账号", "过期无缓存", "过期有缓存", "缺少手机号")) {
                    isolatedStore.accounts().forEach { isolatedStore.remove(it.uid) }
                    if (scenario != "无账号") {
                        isolatedStore.upsert("123456789", if (scenario == "缺少手机号") "" else "13800000000", "")
                        if (scenario == "过期有缓存") {
                            isolatedStore.putRecords("123456789", 3, listOf(GachaRecord(1, 1, 100L, 1)))
                            isolatedStore.save()
                        }
                    }
                    for (method in listOf("smartRefresh", "showExportKey")) {
                        val name = "$scenario/$method"
                        var dialog: android.app.Dialog? = null
                        try {
                            MainActivity::class.java.getDeclaredMethod(method).apply { isAccessible = true }.invoke(screen)
                            dialog = MainActivity::class.java.getDeclaredField("reauthDialog")
                                .apply { isAccessible = true }.get(screen) as android.app.Dialog
                            check(dialog.isShowing)
                            val positive = dialog.findViewById<android.widget.Button>(android.R.id.button1)
                            check(positive.text.toString() == if (scenario == "无账号" || scenario == "缺少手机号") "添加账号" else "发送验证码")
                            dialog.findViewById<android.widget.Button>(android.R.id.button2).performClick()
                            // 按钮默认通过消息队列关闭，当前主线程回调内先显式收起再检查。
                            dialog.dismiss()
                            check(!dialog.isShowing)
                            check(MainActivity::class.java.getDeclaredField("reauthBusy").apply { isAccessible = true }.get(screen) == false)
                            if (scenario == "过期有缓存") check(isolatedStore.current()?.records?.get(3)?.size == 1)
                            passed++
                        } catch (e: Exception) { failures.add(name) }
                        finally { dialog?.dismiss() }
                    }
                }
            }
        } catch (e: Exception) { failures.add("界面测试初始化") }
        finally {
            activity?.let { screen -> runOnMainSync { screen.finish() } }
            isolatedDir.deleteRecursively()
        }
        finish(if (failures.isEmpty()) Activity.RESULT_OK else Activity.RESULT_CANCELED, Bundle().apply {
            putInt("passed", passed)
            putInt("failed", failures.size)
            putString("stream", "续登确认测试：通过 $passed，失败 ${failures.size}；" + failures.joinToString("、"))
        })
    }

    /** 可选联调：只在手动点击导出后运行，只返回布尔结果，绝不打印真实钥匙。 */
    private fun verifyExportedClipboard() {
        var matches = false
        var sensitive = false
        try {
            val monitor = addMonitor(MainActivity::class.java.name, null, false)
            val activity = try {
                // 从测试的 shell 通道启动，避免新版 Android 拦截后台 Activity 启动后一直等待。
                val command = "am start -n ${targetContext.packageName}/${MainActivity::class.java.name}"
                android.os.ParcelFileDescriptor.AutoCloseInputStream(uiAutomation.executeShellCommand(command))
                    .use { it.readBytes() }
                waitForMonitorWithTimeout(monitor, 5000) ?: error("主界面启动超时")
            } finally {
                removeMonitor(monitor)
            }
            val deadline = android.os.SystemClock.elapsedRealtime() + 2000
            while (!activity.hasWindowFocus() && android.os.SystemClock.elapsedRealtime() < deadline) {
                android.os.SystemClock.sleep(50)
            }
            runOnMainSync {
                val clipboard = targetContext.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clip = clipboard.primaryClip
                val key = clip?.getItemAt(0)?.text?.toString().orEmpty()
                if (key.startsWith("XKL1.")) {
                    val json = JSONObject(String(Base64.decode(key.substring(5), Base64.URL_SAFE), Charsets.UTF_8))
                    val account = AccountStore(targetContext).current()
                    matches = account != null && json.length() == 3 && json.getInt("version") == 1 &&
                        json.getString("uid") == account.uid && json.getString("credential") == account.token
                    sensitive = clip?.description?.extras?.getBoolean(ClipDescription.EXTRA_IS_SENSITIVE) == true
                }
            }
        } catch (e: Exception) {
            // 真实账号与凭证只在内存中比对。
        }
        finish(if (matches && sensitive) Activity.RESULT_OK else Activity.RESULT_CANCELED, Bundle().apply {
            putBoolean("matchesCurrentAccount", matches)
            putBoolean("sensitiveClipboard", sensitive)
            putString("stream", "实际导出校验：账号匹配=$matches，敏感剪贴板=$sensitive")
        })
    }
}
