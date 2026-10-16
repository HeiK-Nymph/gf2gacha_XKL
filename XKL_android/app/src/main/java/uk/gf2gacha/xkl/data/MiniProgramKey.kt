package uk.gf2gacha.xkl.data

import android.content.ClipData
import android.content.ClipDescription
import android.os.PersistableBundle
import android.util.Base64
import org.json.JSONObject

/** 小程序导入协议 v1。只封装 UID 和现有凭证，不包含手机号、密码或抽卡记录。 */
object MiniProgramKey {
    fun encode(uid: String, credential: String): String {
        require(uid.matches(Regex("[0-9]{4,32}"))) { "UID 格式不正确" }
        require(credential.isNotBlank() && credential.length <= 4096 &&
            !credential.contains('\r') && !credential.contains('\n')) { "凭证格式不正确" }
        val json = JSONObject().apply {
            put("version", 1)
            put("uid", uid)
            put("credential", credential)
        }
        val payload = Base64.encodeToString(
            json.toString().toByteArray(Charsets.UTF_8),
            Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING
        )
        return "XKL1.$payload"
    }

    /** Android 13+ 隐藏剪贴板预览中的钥匙内容，旧系统忽略这一标记。 */
    fun clip(key: String): ClipData = ClipData.newPlainText("小程序导入钥匙", key).apply {
        description.extras = PersistableBundle().apply {
            putBoolean(ClipDescription.EXTRA_IS_SENSITIVE, true)
        }
    }
}
