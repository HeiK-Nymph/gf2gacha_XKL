package uk.gf2gacha.xkl.data

import kotlinx.coroutines.ensureActive
import kotlin.coroutines.coroutineContext

data class BiliVerificationChallenge(
    val type: String,
    val token: String,
    val gt: String = "",
    val challenge: String = "",
    val userId: String = "",
    val online: Boolean = true,
    val imageUrl: String = ""
)

data class BiliVerificationProof(val parameters: Map<String, String>) {
    companion object {
        fun fromGeetest(challenge: BiliVerificationChallenge, payload: String): BiliVerificationProof {
            require(challenge.type == "1" && payload.length <= 4096)
            val json = org.json.JSONObject(payload)
            val values = listOf("challenge", "validate", "seccode").associateWith { key ->
                json.getString(key).also { require(it.isNotBlank() && it.length <= 512 && '\r' !in it && '\n' !in it) }
            }
            return BiliVerificationProof(values + mapOf("captcha_type" to "1", "ctoken" to challenge.token,
                "gt_user_id" to challenge.userId))
        }
    }
}

class BiliVerificationRequired(val code: Int) : Exception("需要完成B站安全验证")
class BiliVerificationCancelled : Exception("已取消安全验证")

/** A successful first response never opens verification; one human proof permits one resubmission. */
object BiliPasswordFlow {
    suspend fun authenticate(
        business: Map<String, String>,
        attempt: (Map<String, String>) -> org.json.JSONObject,
        challenge: (Int) -> BiliVerificationChallenge,
        verify: suspend (BiliVerificationChallenge) -> BiliVerificationProof
    ): org.json.JSONObject {
        coroutineContext.ensureActive()
        return try {
            attempt(business)
        } catch (required: BiliVerificationRequired) {
            coroutineContext.ensureActive()
            val proof = verify(challenge(required.code))
            coroutineContext.ensureActive()
            attempt(business + proof.parameters)
        }
    }
}
