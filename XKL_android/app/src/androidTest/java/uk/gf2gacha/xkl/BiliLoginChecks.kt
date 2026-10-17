package uk.gf2gacha.xkl

import android.content.Context
import android.content.ContextWrapper
import android.os.Bundle
import kotlinx.coroutines.runBlocking
import uk.gf2gacha.xkl.data.AccountStore
import uk.gf2gacha.xkl.data.BiliAuth
import uk.gf2gacha.xkl.data.GameChannel
import uk.gf2gacha.xkl.data.GachaRecord
import uk.gf2gacha.xkl.data.Gf2Exception
import uk.gf2gacha.xkl.data.SmsChallenge
import uk.gf2gacha.xkl.data.BiliPasswordFlow
import uk.gf2gacha.xkl.data.BiliVerificationChallenge
import uk.gf2gacha.xkl.data.BiliVerificationProof
import uk.gf2gacha.xkl.data.BiliVerificationRequired
import uk.gf2gacha.xkl.data.BiliVerificationCancelled
import android.util.Base64
import org.json.JSONObject
import java.security.KeyPairGenerator
import javax.crypto.Cipher
import java.io.File

/** Device integration checks; never send SMS or use real saved accounts. */
object BiliLoginChecks {
    fun run(context: Context): Bundle {
        val failures = mutableListOf<String>()
        var passed = 0
        fun verify(name: String, action: () -> Unit) {
            try { action(); passed++ } catch (e: Throwable) { failures.add(name + ": " + e.javaClass.simpleName) }
        }
        val directory = File(context.cacheDir, "bili-tests-${System.nanoTime()}").apply { mkdirs() }
        val isolated = object : ContextWrapper(context) { override fun getFilesDir(): File = directory }
        try {
            verify("legacy account migration and same-UID channel isolation") {
                File(directory, "accounts.json").writeText(
                    """{"current":"123456789","accounts":[{"uid":"123456789","token":"official-fixture"}]}"""
                )
                val store = AccountStore(isolated)
                check(store.current()?.channel == GameChannel.OFFICIAL)
                val official = store.current()!!
                val bili = store.upsert(official.uid, "", "bili-fixture", GameChannel.BILIBILI)
                check(store.accounts().size == 2 && official.key != bili.key)
                store.putRecords(official.key, 3, listOf(GachaRecord(1, 1001, 1, 1)))
                store.putRecords(bili.key, 3, listOf(GachaRecord(1, 2002, 2, 1)))
                store.save()
                val restored = AccountStore(isolated)
                check(restored.current()?.key == bili.key)
                check(restored.select(official.key)?.records?.get(3)?.single()?.itemId == 1001)
                check(restored.select(bili.key)?.records?.get(3)?.single()?.itemId == 2002)
                restored.invalidateToken(bili.key)
                check(restored.select(official.key)?.token == "official-fixture")
                check(restored.remove(official.key) && restored.accounts().single().channel == GameChannel.BILIBILI)
                check(restored.current()?.token == "")
            }
            verify("wrong phone or channel challenge rejected before network") {
                runBlocking {
                    for (challenge in listOf(null, SmsChallenge("10000000000", GameChannel.OFFICIAL),
                        SmsChallenge("10000000001", GameChannel.BILIBILI, "fixture"))) {
                        var rejected = false
                        try { BiliAuth.login(context, "10000000000", "000000", challenge) }
                        catch (e: Gf2Exception) { rejected = e.message?.contains("发送B服验证码") == true }
                        check(rejected)
                    }
                }
            }
            verify("native headers and signed SDK config in app process") {
                check(runBlocking { BiliAuth.verifyConfiguration(context) })
            }
            val fixtureChallenge = BiliVerificationChallenge("1", "fixture-token", "fixture-gt", "original", "fixture-user")
            val fixtureProof = BiliVerificationProof.fromGeetest(fixtureChallenge,
                """{"challenge":"completed","validate":"fixture-validation","seccode":"fixture-code"}""")
            val business = mapOf("user_id" to "fixture-user", "pwd" to "encrypted-fixture")
            verify("successful password login skips all verification work") {
                var attempts = 0
                val result = runBlocking {
                    BiliPasswordFlow.authenticate(business, { attempts++; JSONObject().put("code", 0) },
                        { error("Must not request verification") }, { error("Must not open verification UI") })
                }
                check(result.getInt("code") == 0 && attempts == 1)
            }
            verify("required verification resumes the same login with human proof") {
                var attempts = 0
                var windows = 0
                runBlocking {
                    BiliPasswordFlow.authenticate(business, { params ->
                        attempts++
                        if (attempts == 1) throw BiliVerificationRequired(200007)
                        check(params["pwd"] == "encrypted-fixture" && params["user_id"] == "fixture-user")
                        check(params["ctoken"] == "fixture-token" && params["validate"] == "fixture-validation")
                        JSONObject().put("code", 0)
                    }, { fixtureChallenge }, { windows++; fixtureProof })
                }
                check(attempts == 2 && windows == 1)
            }
            verify("cancelled verification never resubmits a password") {
                var attempts = 0
                var cancelled = false
                try {
                    runBlocking {
                        BiliPasswordFlow.authenticate(business, { attempts++; throw BiliVerificationRequired(200007) },
                            { fixtureChallenge }, { throw BiliVerificationCancelled() })
                    }
                } catch (e: BiliVerificationCancelled) { cancelled = true }
                check(cancelled && attempts == 1)
            }
            verify("invalid credentials do not open CAPTCHA or retry") {
                var attempts = 0
                var rejected = false
                try {
                    runBlocking {
                        BiliPasswordFlow.authenticate(business, { attempts++; throw Gf2Exception(-629, "fixture") },
                            { error("Must not fetch CAPTCHA") }, { error("Must not open CAPTCHA") })
                    }
                } catch (e: Gf2Exception) { rejected = true }
                check(rejected && attempts == 1)
            }
            verify("repeated CAPTCHA requirement is bounded to one verified resubmission") {
                var attempts = 0
                var windows = 0
                try {
                    runBlocking {
                        BiliPasswordFlow.authenticate(business, { attempts++; throw BiliVerificationRequired(200005) },
                            { fixtureChallenge }, { windows++; fixtureProof })
                    }
                } catch (e: BiliVerificationRequired) { /* Explicit user retry is required. */ }
                check(attempts == 2 && windows == 1)
            }
            verify("dynamic RSA password encryption preserves prefix and UTF-8 without double encoding") {
                val pair = KeyPairGenerator.getInstance("RSA").apply { initialize(1024) }.generateKeyPair()
                val pem = "-----BEGIN PUBLIC KEY-----\n" + Base64.encodeToString(pair.public.encoded, Base64.NO_WRAP) +
                    "\n-----END PUBLIC KEY-----"
                val encoded = BiliAuth.encryptPassword("fixture-prefix", "测试密码+&", pem)
                val decoder = Cipher.getInstance("RSA/ECB/PKCS1Padding").apply { init(Cipher.DECRYPT_MODE, pair.private) }
                check(String(decoder.doFinal(Base64.decode(encoded, Base64.DEFAULT)), Charsets.UTF_8) == "fixture-prefix测试密码+&")
            }
            verify("malformed CAPTCHA callback is rejected without account data") {
                var rejected = false
                try { BiliVerificationProof.fromGeetest(fixtureChallenge,
                    """{"challenge":"done","validate":"","seccode":"code"}""") }
                catch (e: IllegalArgumentException) { rejected = true }
                check(rejected)
            }
        } finally {
            directory.deleteRecursively()
        }
        return Bundle().apply {
            putInt("passed", passed)
            putInt("failed", failures.size)
            putString("failures", failures.joinToString("; "))
        }
    }
}
