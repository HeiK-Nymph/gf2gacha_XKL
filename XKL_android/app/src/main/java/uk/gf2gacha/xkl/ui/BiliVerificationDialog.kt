package uk.gf2gacha.xkl.ui

import android.annotation.SuppressLint
import android.app.Activity
import android.graphics.Color
import android.net.Uri
import android.text.InputFilter
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import androidx.appcompat.app.AlertDialog
import coil.load
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import org.json.JSONObject
import uk.gf2gacha.xkl.R
import uk.gf2gacha.xkl.data.BiliVerificationCancelled
import uk.gf2gacha.xkl.data.BiliVerificationChallenge
import uk.gf2gacha.xkl.data.BiliVerificationProof
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** The WebView receives only CAPTCHA data, never the username, password or account token. */
object BiliVerificationDialog {
    @SuppressLint("SetJavaScriptEnabled") // Required by the provider's human-operated CAPTCHA.
    suspend fun show(activity: Activity, challenge: BiliVerificationChallenge): BiliVerificationProof =
        withContext(Dispatchers.Main) {
            suspendCancellableCoroutine { continuation ->
                val density = activity.resources.displayMetrics.density
                fun dp(value: Int) = (density * value).toInt()
                var webView: WebView? = null
                val content = FrameLayout(activity)
                val dialog = MaterialAlertDialogBuilder(activity)
                    .setTitle(R.string.bili_verification_title)
                    .setView(content)
                    .setNegativeButton(R.string.login_cancel, null)
                    .create()
                fun finishVerification(proof: BiliVerificationProof) {
                    if (!continuation.isActive) return
                    continuation.resume(proof)
                    dialog.dismiss()
                }
                dialog.setOnDismissListener {
                    webView?.let { web ->
                        web.stopLoading()
                        web.removeJavascriptInterface("BiliCaptcha")
                        (web.parent as? ViewGroup)?.removeView(web)
                        web.destroy()
                    }
                    webView = null
                    if (continuation.isActive) continuation.resumeWithException(BiliVerificationCancelled())
                }
                if (challenge.type == "1") {
                    val web = WebView(activity)
                    webView = web
                    web.setBackgroundColor(Color.rgb(20, 23, 28))
                    web.isSaveEnabled = false
                    web.settings.apply {
                        javaScriptEnabled = true
                        domStorageEnabled = true
                        allowFileAccess = false
                        allowContentAccess = false
                        mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
                        setSupportMultipleWindows(false)
                    }
                    web.webViewClient = object : WebViewClient() {
                        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                            request.isForMainFrame // Keep the bridge on our controlled page.
                    }
                    val config = JSONObject().apply {
                        put("gt", challenge.gt)
                        put("challenge", challenge.challenge)
                        put("offline", !challenge.online)
                    }.toString().replace("<", "\\u003c")
                    val html = activity.assets.open("bili_verification.html").bufferedReader().use { it.readText() }
                        .replace("__BILI_CAPTCHA_CONFIG__", config)
                    fun loadPage() = web.loadDataWithBaseURL("https://game.bilibili.com/sdk/geetest/", html, "text/html", "UTF-8", null)
                    web.addJavascriptInterface(object {
                        @JavascriptInterface
                        fun reload() {
                            activity.runOnUiThread { if (continuation.isActive) loadPage() }
                        }
                        @JavascriptInterface
                        fun complete(payload: String) {
                            activity.runOnUiThread {
                                if (!continuation.isActive) return@runOnUiThread
                                try {
                                    finishVerification(BiliVerificationProof.fromGeetest(challenge, payload))
                                } catch (e: Exception) {
                                    // Ignore malformed/unrelated callbacks without exposing their content.
                                }
                            }
                        }
                    }, "BiliCaptcha")
                    val height = (activity.resources.displayMetrics.heightPixels * .58f).toInt().coerceAtMost(dp(500))
                    content.addView(web, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, height))
                    loadPage()
                } else if (challenge.type == "2") {
                    val column = LinearLayout(activity).apply {
                        orientation = LinearLayout.VERTICAL
                        setPadding(dp(24), dp(12), dp(24), dp(12))
                    }
                    val image = ImageView(activity).apply {
                        adjustViewBounds = true
                        contentDescription = activity.getString(R.string.bili_verification_image)
                    }
                    val input = EditText(activity).apply {
                        hint = activity.getString(R.string.bili_verification_image_hint)
                        isSingleLine = true
                        isSaveEnabled = false
                        filters = arrayOf(InputFilter.LengthFilter(32))
                    }
                    column.addView(image, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(120)))
                    column.addView(input)
                    content.addView(column)
                    if (Uri.parse(challenge.imageUrl).scheme == "https") image.load(challenge.imageUrl)
                    dialog.setButton(AlertDialog.BUTTON_POSITIVE, activity.getString(R.string.bili_verification_submit)) { _, _ -> }
                    dialog.setOnShowListener {
                        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                            val code = input.text.toString().trim()
                            if (code.isBlank()) input.error = activity.getString(R.string.bili_verification_image_hint)
                            else finishVerification(BiliVerificationProof(mapOf("captcha_type" to "2", "ctoken" to challenge.token,
                                "img_code" to code, "captcha_code" to code, "image_token" to challenge.token)))
                        }
                    }
                }
                continuation.invokeOnCancellation { activity.runOnUiThread { dialog.dismiss() } }
                if (continuation.isActive) dialog.show()
            }
        }
}
