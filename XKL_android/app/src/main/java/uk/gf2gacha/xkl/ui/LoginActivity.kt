package uk.gf2gacha.xkl.ui

import android.os.Bundle
import android.text.InputFilter
import android.text.InputType
import android.view.View
import android.os.CountDownTimer
import android.os.SystemClock
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.RadioGroup
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.CancellationException
import uk.gf2gacha.xkl.R
import uk.gf2gacha.xkl.data.AccountStore
import uk.gf2gacha.xkl.data.BiliAuth
import uk.gf2gacha.xkl.data.BiliVerificationCancelled
import uk.gf2gacha.xkl.data.Gf2Api
import uk.gf2gacha.xkl.data.Gf2Exception
import uk.gf2gacha.xkl.data.GameChannel
import uk.gf2gacha.xkl.data.SmsChallenge

/**
 * 添加账号：手机号 + 短信验证码登录（默认），也可切到账号密码登录。
 *
 * 官服密码使用官方MD5协议，B服使用动态RSA公钥；需要安全验证时在应用内完成。
 * 密码不写入账号文件或实例状态。
 *
 * 登录成功只做两件事：把账号（uid/手机号/令牌）写进 AccountStore，然后关掉本页回主界面。
 * **不会碰其它账号的数据**；用户中途取消/失败，主界面状态原样保留。
 */
class LoginActivity : AppCompatActivity() {

    companion object { const val EXTRA_CHANNEL = "login_channel" }

    private lateinit var phoneInput: EditText
    private lateinit var codeInput: EditText
    private lateinit var sendButton: Button
    private lateinit var loginButton: Button
    private lateinit var statusView: TextView
    private lateinit var pwdInput: EditText
    private lateinit var pwdNote: TextView
    private lateinit var modeSwitch: TextView
    private var timer: CountDownTimer? = null
    private lateinit var channelGroup: RadioGroup
    private var channel = GameChannel.OFFICIAL
    private var challenge: SmsChallenge? = null
    private var resendAt = 0L
    private var busy = false

    /** false = 短信验证码登录（默认）；true = 账号密码登录 */
    private var pwdMode = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login)

        phoneInput = findViewById(R.id.phone_input)
        codeInput = findViewById(R.id.code_input)
        sendButton = findViewById(R.id.send_button)
        loginButton = findViewById(R.id.login_button)
        statusView = findViewById(R.id.status_view)
        pwdInput = findViewById(R.id.pwd_input)
        pwdNote = findViewById(R.id.pwd_note)
        modeSwitch = findViewById(R.id.mode_switch)
        channelGroup = findViewById(R.id.channel_group)
        channel = GameChannel.fromId(savedInstanceState?.getInt("channel") ?: intent.getIntExtra(EXTRA_CHANNEL, 5))
        resendAt = savedInstanceState?.getLong("resendAt", 0L) ?: 0L
        savedInstanceState?.getString("challengePhone")?.let { phone ->
            challenge = SmsChallenge(phone, channel, savedInstanceState.getString("captchaKey", ""))
        }
        channelGroup.check(if (channel == GameChannel.BILIBILI) R.id.channel_bili else R.id.channel_official)
        updateChannel()
        switchMode(savedInstanceState?.getBoolean("pwdMode", false) == true)
        if (resendAt > SystemClock.elapsedRealtime()) startCountdown()
        channelGroup.setOnCheckedChangeListener { _, checked ->
            channel = if (checked == R.id.channel_bili) GameChannel.BILIBILI else GameChannel.OFFICIAL
            challenge = null
            codeInput.setText("")
            pwdInput.setText("")
            switchMode(false)
            updateChannel()
        }

        sendButton.setOnClickListener { sendCode() }
        loginButton.setOnClickListener { login() }
        findViewById<Button>(R.id.cancel_button).setOnClickListener { finish() }
        modeSwitch.setOnClickListener { switchMode(!pwdMode) }
    }

    /** 在「短信验证码」和「账号密码」两种登录方式之间切换 */
    private fun switchMode(toPwd: Boolean) {
        pwdMode = toPwd
        sendButton.visibility = if (toPwd) View.GONE else View.VISIBLE
        codeInput.visibility = if (toPwd) View.GONE else View.VISIBLE
        pwdInput.visibility = if (toPwd) View.VISIBLE else View.GONE
        pwdNote.visibility = if (toPwd) View.VISIBLE else View.GONE
        val biliPassword = toPwd && channel == GameChannel.BILIBILI
        phoneInput.inputType = if (biliPassword) InputType.TYPE_CLASS_TEXT else InputType.TYPE_CLASS_PHONE
        phoneInput.filters = arrayOf(InputFilter.LengthFilter(if (biliPassword) 100 else 11))
        pwdInput.filters = arrayOf(InputFilter.LengthFilter(if (biliPassword) 128 else 32))
        pwdNote.setText(if (biliPassword) R.string.login_bili_pwd_note else R.string.login_pwd_note)
        // B服账号密码可使用手机号、用户名或邮箱；短信模式仍要求手机号。
        phoneInput.hint = getString(
            if (toPwd) R.string.login_account_hint else R.string.login_phone_hint
        )
        modeSwitch.text = getString(
            if (toPwd) R.string.login_switch_to_sms else R.string.login_switch_to_pwd
        )
        loginButton.text = getString(
            if (toPwd) R.string.login_submit_pwd else R.string.login_submit
        )
        setStatus("")
        updateChannel()
    }

    private fun updateChannel() {
        modeSwitch.visibility = View.VISIBLE
        findViewById<TextView>(R.id.login_hint).text = when {
            channel == GameChannel.BILIBILI && pwdMode -> getString(R.string.login_bili_password_hint)
            channel == GameChannel.BILIBILI -> getString(R.string.login_bili_hint)
            else -> getString(R.string.login_hint)
        }
    }

    private fun setBusy(value: Boolean) {
        busy = value
        phoneInput.isEnabled = !value
        pwdInput.isEnabled = !value
        codeInput.isEnabled = !value
        modeSwitch.isEnabled = !value
        loginButton.isEnabled = !value
        sendButton.isEnabled = !value && SystemClock.elapsedRealtime() >= resendAt
        for (i in 0 until channelGroup.childCount) channelGroup.getChildAt(i).isEnabled = !value
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putInt("channel", channel.id)
        outState.putBoolean("pwdMode", pwdMode)
        outState.putLong("resendAt", resendAt)
        challenge?.let {
            outState.putString("challengePhone", it.phone)
            outState.putString("captchaKey", it.captchaKey)
        }
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        timer?.cancel()
        super.onDestroy()
    }

    private fun sendCode() {
        if (busy || SystemClock.elapsedRealtime() < resendAt) return
        val phone = phoneInput.text.toString().trim()
        if (phone.length != 11 || !phone.all { it.isDigit() }) {
            toast("请输入 11 位手机号")
            return
        }
        setBusy(true)
        challenge = null
        resendAt = SystemClock.elapsedRealtime() + 60_000L
        startCountdown()
        setStatus("正在发送验证码…")
        lifecycleScope.launch {
            try {
                challenge = Gf2Api.sendSmsCode(this@LoginActivity, phone, channel)
                setStatus("验证码已发送，请查看短信后填到下面")
            } catch (e: Exception) {
                setStatus("发送失败：" + describe(e))
            } finally {
                setBusy(false)
            }
        }
    }

    private fun login() {
        if (busy) return
        val account = phoneInput.text.toString().trim()
        if (pwdMode && channel == GameChannel.BILIBILI) {
            if (account.isBlank()) { toast("请输入B站账号"); return }
            loginWithPassword(account)
            return
        }
        if (account.length != 11 || !account.all { it.isDigit() }) {
            toast("请输入 11 位手机号")
            return
        }
        if (pwdMode) loginWithPassword(account) else loginWithSms(account)
    }

    private fun loginWithSms(phone: String) {
        val code = codeInput.text.toString().trim()
        if (code.length != 6 || !code.all { it.isDigit() }) {
            toast("请输入 6 位验证码")
            return
        }
        setBusy(true)
        setStatus("正在登录…")
        lifecycleScope.launch {
            try {
                val result = Gf2Api.smsLogin(this@LoginActivity, phone, code, channel, challenge)
                onLoggedIn(result.uid, phone, result.accessToken)
            } catch (e: Exception) {
                setStatus("登录失败：" + describe(e))
            } finally {
                setBusy(false)
            }
        }
    }

    /** 只在本次登录内使用密码；B服仅在服务端要求时显示验证窗口。 */
    private fun loginWithPassword(account: String) {
        val pwd = pwdInput.text.toString()
        if (channel == GameChannel.OFFICIAL && (pwd.length < 6 || pwd.length > 20)) {
            toast("密码长度应为 6–20 位")
            return
        }
        if (pwd.isEmpty()) { toast("请输入密码"); return }
        pwdInput.setText("")
        setBusy(true)
        setStatus("正在登录…")
        lifecycleScope.launch {
            try {
                val result = if (channel == GameChannel.BILIBILI) {
                    BiliAuth.passwordLogin(this@LoginActivity, account, pwd) { verification ->
                        kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.Main) {
                            setStatus("请在验证窗口完成B站安全验证")
                        }
                        val proof = BiliVerificationDialog.show(this@LoginActivity, verification)
                        kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.Main) {
                            setStatus("验证完成，正在登录…")
                        }
                        proof
                    }
                } else Gf2Api.passwordLogin(this@LoginActivity, account, pwd)
                onLoggedIn(result.uid, account, result.accessToken)
            } catch (e: BiliVerificationCancelled) {
                setStatus("已取消安全验证，可重新登录")
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                setStatus("登录失败：" + describe(e))
            } finally {
                setBusy(false)
            }
        }
    }

    private fun onLoggedIn(uid: String, phone: String, accessToken: String) {
        val mobile = phone.takeIf { it.length == 11 && it.all(Char::isDigit) }.orEmpty()
        AccountStore(this@LoginActivity).upsert(uid, mobile, accessToken, channel)
        toast("账号已添加：uid=" + uid)
        finish()
    }

    private fun startCountdown() {
        timer?.cancel()
        sendButton.isEnabled = false
        timer = object : CountDownTimer((resendAt - SystemClock.elapsedRealtime()).coerceAtLeast(1L), 1_000L) {
            override fun onTick(millisUntilFinished: Long) {
                sendButton.text = "重新发送(" + millisUntilFinished / 1000 + "s)"
            }

            override fun onFinish() {
                sendButton.isEnabled = !busy
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
