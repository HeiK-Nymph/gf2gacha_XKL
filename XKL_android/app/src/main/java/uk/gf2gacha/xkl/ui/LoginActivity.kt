package uk.gf2gacha.xkl.ui

import android.os.Bundle
import android.os.CountDownTimer
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import uk.gf2gacha.xkl.R
import uk.gf2gacha.xkl.data.AccountStore
import uk.gf2gacha.xkl.data.Gf2Api
import uk.gf2gacha.xkl.data.Gf2Exception

/**
 * 添加账号：手机号 + 短信验证码登录。
 *
 * 登录成功只做两件事：把账号（uid/手机号/令牌）写进 AccountStore，然后关掉本页回主界面。
 * **不会碰其它账号的数据**；用户中途取消/失败，主界面状态原样保留。
 */
class LoginActivity : AppCompatActivity() {

    private lateinit var phoneInput: EditText
    private lateinit var codeInput: EditText
    private lateinit var sendButton: Button
    private lateinit var loginButton: Button
    private lateinit var statusView: TextView
    private var timer: CountDownTimer? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login)

        phoneInput = findViewById(R.id.phone_input)
        codeInput = findViewById(R.id.code_input)
        sendButton = findViewById(R.id.send_button)
        loginButton = findViewById(R.id.login_button)
        statusView = findViewById(R.id.status_view)

        sendButton.setOnClickListener { sendCode() }
        loginButton.setOnClickListener { login() }
        findViewById<Button>(R.id.cancel_button).setOnClickListener { finish() }
    }

    override fun onDestroy() {
        timer?.cancel()
        super.onDestroy()
    }

    private fun sendCode() {
        val phone = phoneInput.text.toString().trim()
        if (phone.length != 11 || !phone.all { it.isDigit() }) {
            toast("请输入 11 位手机号")
            return
        }
        sendButton.isEnabled = false
        startCountdown()
        setStatus("正在发送验证码…")
        lifecycleScope.launch {
            try {
                Gf2Api.sendSmsCode(this@LoginActivity, phone)
                setStatus("验证码已发送，请查看短信后填到下面")
            } catch (e: Exception) {
                setStatus("发送失败：" + describe(e))
            }
        }
    }

    private fun login() {
        val phone = phoneInput.text.toString().trim()
        val code = codeInput.text.toString().trim()
        if (phone.length != 11 || !phone.all { it.isDigit() }) {
            toast("请输入 11 位手机号")
            return
        }
        if (code.length != 6 || !code.all { it.isDigit() }) {
            toast("请输入 6 位验证码")
            return
        }
        loginButton.isEnabled = false
        setStatus("正在登录…")
        lifecycleScope.launch {
            try {
                val result = Gf2Api.smsLogin(this@LoginActivity, phone, code)
                AccountStore(this@LoginActivity).upsert(result.uid, phone, result.accessToken)
                toast("账号已添加：uid=" + result.uid)
                finish()
            } catch (e: Exception) {
                setStatus("登录失败：" + describe(e))
            } finally {
                loginButton.isEnabled = true
            }
        }
    }

    private fun startCountdown() {
        timer?.cancel()
        timer = object : CountDownTimer(60_000L, 1_000L) {
            override fun onTick(millisUntilFinished: Long) {
                sendButton.text = "重新发送(" + millisUntilFinished / 1000 + "s)"
            }

            override fun onFinish() {
                sendButton.isEnabled = true
                sendButton.text = "发送验证码"
            }
        }.start()
    }

    private fun setStatus(text: String) {
        statusView.text = text
    }

    private fun describe(e: Exception): String =
        if (e is Gf2Exception) "code=" + e.code + " " + (e.message ?: "") else (e.message ?: e.javaClass.simpleName)

    private fun toast(text: String) {
        Toast.makeText(this, text, Toast.LENGTH_SHORT).show()
    }
}