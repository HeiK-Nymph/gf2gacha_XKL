package uk.gf2gacha.xkl.ui

import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import uk.gf2gacha.xkl.R
import uk.gf2gacha.xkl.data.Account
import uk.gf2gacha.xkl.data.AccountStore
import uk.gf2gacha.xkl.data.CommunityApi
import uk.gf2gacha.xkl.data.CommunityException
import uk.gf2gacha.xkl.data.CommunitySnapshot
import uk.gf2gacha.xkl.data.CommunityStore
import uk.gf2gacha.xkl.data.CommunityToken
import uk.gf2gacha.xkl.data.GameChannel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 社区签到页（独立页面，左上角返回与登录页一致）。
 *
 * 按钮语义与 PC 端一致：
 *  - 未绑定：底部只露「绑定社区」，一键按钮禁用；
 *  - 已绑定：「刷新状态」只读、「重新绑定」换票（换号用）、「一键」执行；
 *  - 首次进页面不会偷偷换票，只有「绑过但过期」才自动续期。
 */
class CommunityActivity : AppCompatActivity() {

    private lateinit var store: AccountStore
    private lateinit var communityStore: CommunityStore
    private lateinit var account: Account

    private lateinit var hint: TextView
    private lateinit var accountView: TextView
    private lateinit var tasksBox: LinearLayout
    private lateinit var rewardsBox: LinearLayout
    private lateinit var stepsBox: LinearLayout
    private lateinit var refreshBtn: Button
    private lateinit var rebindBtn: Button
    private lateinit var runBtn: Button

    private var bound = false
    private var busy = false
    private var tokenExp = 0L
    private var firstResume = true

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = AccountStore(this)
        val current = store.current()
        if (current == null) {
            Toast.makeText(this, "请先登录账号", Toast.LENGTH_SHORT).show()
            finish()
            return
        }
        if (current.channel != GameChannel.OFFICIAL) {
            Toast.makeText(this, "B服账号暂不支持社区功能", Toast.LENGTH_SHORT).show()
            finish()
            return
        }
        account = current
        communityStore = CommunityStore(this)

        setContentView(R.layout.activity_community)

        // 底部固定按钮要避开导航栏/手势区（部分机器该区域没有 inset）
        findViewById<View>(R.id.community_bottom).applyBottomSafeInset()

        findViewById<View>(R.id.back_button).setOnClickListener { finish() }

        hint = findViewById(R.id.community_hint)
        accountView = findViewById(R.id.community_account)
        tasksBox = findViewById(R.id.community_tasks)
        rewardsBox = findViewById(R.id.community_rewards)
        stepsBox = findViewById(R.id.community_steps)
        refreshBtn = findViewById(R.id.community_refresh)
        rebindBtn = findViewById(R.id.community_rebind)
        runBtn = findViewById(R.id.community_run)

        refreshBtn.setOnClickListener { refresh() }
        rebindBtn.setOnClickListener { bind() }
        runBtn.setOnClickListener { oneClick() }

        renderState()
        refresh()
    }

    override fun onResume() {
        super.onResume()
        // 从登录页回来时凭证可能已换新，重新读一次
        if (firstResume) {
            firstResume = false
            return
        }
        refresh()
    }

    // ------------------------------------------------------------ 动作

    private fun refresh() {
        if (busy) return
        busy = true
        renderState()

        lifecycleScope.launch {
            try {
                val cached = communityStore.get(account.key)
                if (cached == null) {
                    bound = false
                    hint.text = "尚未绑定：点下方「绑定社区」，会用当前账号的登录凭证换一张社区票。"
                    accountView.text = ""
                    tasksBox.removeAllViews()
                    rewardsBox.removeAllViews()
                    return@launch
                }
                hint.text = "读取中…"
                val token = withContext(Dispatchers.IO) { ensureToken(cached) }
                val snapshot = withContext(Dispatchers.IO) { CommunityApi.snapshot(token) }
                tokenExp = token.exp
                bound = true
                hint.text = ""
                renderSnapshot(snapshot)
            } catch (e: CommunityException) {
                if (e.code == 401) {
                    bound = false
                    communityStore.remove(account.key)
                }
                hint.text = e.message ?: "读取社区状态失败"
            } catch (e: Exception) {
                hint.text = "读取社区状态失败：${e.message ?: "未知错误"}"
            } finally {
                busy = false
                renderState()
            }
        }
    }

    private fun bind() {
        if (busy) return
        if (account.token.isEmpty()) {
            toast("没有可用的游戏凭证：请先刷新一次抽卡记录或重新登录")
            return
        }
        busy = true
        renderState()
        hint.text = "正在绑定…"

        lifecycleScope.launch {
            try {
                val token = withContext(Dispatchers.IO) {
                    CommunityApi.bind(account.token).also { communityStore.put(account.key, it) }
                }
                tokenExp = token.exp
                bound = true
                val snapshot = withContext(Dispatchers.IO) { CommunityApi.snapshot(token) }
                hint.text = ""
                renderSnapshot(snapshot)
                toast("已绑定社区账号")
            } catch (e: CommunityException) {
                hint.text = e.message ?: "绑定社区失败"
            } catch (e: Exception) {
                hint.text = "绑定社区失败：${e.message ?: "未知错误"}"
            } finally {
                busy = false
                renderState()
            }
        }
    }

    private fun oneClick() {
        if (busy) return
        val token = communityStore.get(account.key)
        if (token == null) {
            toast("请先绑定社区")
            return
        }
        if (!token.isValid()) {
            toast("社区令牌已过期，点「重新绑定」续期")
            return
        }

        busy = true
        renderState()
        hint.text = "正在执行一键流程…"
        stepsBox.removeAllViews()
        addRow(stepsBox, "进行中", "签到 / 每日任务 / 兑换…")

        lifecycleScope.launch {
            try {
                val result = withContext(Dispatchers.IO) { CommunityApi.oneClick(token) }
                stepsBox.removeAllViews()
                result.second.forEach { step ->
                    addRow(stepsBox, step.name, step.message, step.status == "error")
                }
                val snapshot = withContext(Dispatchers.IO) { CommunityApi.snapshot(token) }
                renderSnapshot(snapshot)
                hint.text = ""
            } catch (e: CommunityException) {
                hint.text = e.message ?: "一键流程失败"
            } catch (e: Exception) {
                hint.text = "一键流程失败：${e.message ?: "未知错误"}"
            } finally {
                busy = false
                renderState()
            }
        }
    }

    private fun ensureToken(cached: CommunityToken): CommunityToken {
        if (cached.isValid()) return cached
        // 以前绑过、只是过期：用游戏凭证无感续期；没有凭证就让用户重新登录
        if (account.token.isEmpty()) {
            throw CommunityException(0, "社区令牌已过期，且没有新的游戏凭证：请先刷新抽卡记录或重新登录")
        }
        return CommunityApi.bind(account.token).also { communityStore.put(account.key, it) }
    }

    // ------------------------------------------------------------ 渲染

    private fun renderState() {
        refreshBtn.visibility = if (bound) View.VISIBLE else View.GONE
        rebindBtn.text = if (bound) "重新绑定" else "绑定社区"
        refreshBtn.isEnabled = !busy
        rebindBtn.isEnabled = !busy
        runBtn.isEnabled = bound && !busy
        runBtn.alpha = if (runBtn.isEnabled) 1f else 0.4f
        refreshBtn.alpha = if (refreshBtn.isEnabled) 1f else 0.45f
        rebindBtn.alpha = if (rebindBtn.isEnabled) 1f else 0.45f
    }

    private fun renderSnapshot(snapshot: CommunitySnapshot) {
        val user = snapshot.user
        accountView.text = buildString {
            append(user.nickName.ifEmpty { "—" })
            append("　积分 ").append(user.score)
            append("　Lv.").append(user.level).append("（").append(user.exp).append(" 经验）")
            append(if (user.signedIn) "　今日已签到" else "　今日未签到")
            if (tokenExp > 0) append("　令牌到 ").append(formatTime(tokenExp))
        }

        tasksBox.removeAllViews()
        snapshot.tasks.forEach { task -> addRow(tasksBox, task.name, "${task.done}/${task.max}") }

        rewardsBox.removeAllViews()
        snapshot.rewards.forEach { reward ->
            addRow(
                rewardsBox,
                "${reward.name} ×${reward.count}",
                "需 ${reward.score} 分 · 已换 ${reward.exchanged}/${reward.max}"
            )
        }
    }

    private fun addRow(box: LinearLayout, left: String, right: String, error: Boolean = false) {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, dp(3), 0, dp(3))
        }
        val label = TextView(this).apply {
            text = left
            setTextColor(ContextCompat.getColor(this@CommunityActivity, R.color.text_dim))
            textSize = 12f
        }
        val value = TextView(this).apply {
            text = right
            setTextColor(ContextCompat.getColor(this@CommunityActivity, if (error) R.color.wai_tag else R.color.text))
            textSize = 12f
            gravity = Gravity.END
        }
        row.addView(label, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        row.addView(
            value,
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        )
        box.addView(row)
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun formatTime(seconds: Long): String =
        SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()).format(Date(seconds * 1000))

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }
}
