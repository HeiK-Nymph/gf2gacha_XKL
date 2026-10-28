package uk.gf2gacha.xkl.ui

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.ClipboardManager
import android.content.ContentValues
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.util.Log
import android.text.InputFilter
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.lifecycle.lifecycleScope
import coil.load
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import androidx.appcompat.widget.TooltipCompat
import com.google.android.material.tabs.TabLayout
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import uk.gf2gacha.xkl.R
import uk.gf2gacha.xkl.data.Account
import uk.gf2gacha.xkl.data.AnnouncementCenter
import uk.gf2gacha.xkl.data.GameChannel
import uk.gf2gacha.xkl.data.SmsChallenge
import uk.gf2gacha.xkl.data.AccountStore
import uk.gf2gacha.xkl.data.Gf2Api
import uk.gf2gacha.xkl.data.Gf2Exception
import uk.gf2gacha.xkl.data.MiniProgramKey
import uk.gf2gacha.xkl.data.PoolResult
import uk.gf2gacha.xkl.data.SsrHit
import uk.gf2gacha.xkl.data.SsrTable
import uk.gf2gacha.xkl.data.Titles
import uk.gf2gacha.xkl.data.UpdateChecker
import uk.gf2gacha.xkl.share.ShareCard
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 主界面（启动页）。
 *
 * 访问模型跟 PC 版一致：**直接进抽卡页**，用本地缓存的记录渲染；
 * 顶部三个按钮：添加账号 / 选择账号 / 刷新。
 *
 * - 切账号只切"当前账号"，每个账号各自的 token 和记录都不动（可随时切回、直接刷新）
 * - 刷新：token 还能用就直接拉；不能用就先确认是否发验证码，登录后继续原操作
 */
class MainActivity : AppCompatActivity() {

    private lateinit var store: AccountStore
    private lateinit var uidView: TextView
    private lateinit var titleView: TextView
    private lateinit var heroRow: LinearLayout
    private lateinit var tagsRow: LinearLayout
    private lateinit var statsRow: LinearLayout
    private lateinit var poolStatView: TextView
    private lateinit var ssrList: LinearLayout
    private lateinit var emptyView: TextView
    private lateinit var footer: TextView
    private lateinit var progress: ProgressBar

    private val results = LinkedHashMap<Int, PoolResult>()
    private var current: Gf2Api.Pool = Gf2Api.POOLS[0]
    private var loading = false
    private var renderedUid: String? = null
    private var pendingSave: Bitmap? = null

    /** 五星表来源（底部那行要显示） */
    private var tableSource: String? = null

    /** 更新：检查/下载各一个 job，方便「取消」和防重复 */
    private var updateJob: Job? = null
    private var downloadJob: Job? = null
    private var autoUpdateChecked = false
    private var exportKeyJob: Job? = null
    private var announcementJob: Job? = null
    private var currentAnnouncement: AnnouncementCenter.Announcement? = null
    private var announcementDialog: AlertDialog? = null
    private var reauthDialog: AlertDialog? = null
    private var reauthBusy = false
    private enum class PendingAction { REFRESH, EXPORT }


    // 五星行右侧「歪 + 名字」的固定槽位宽度，必须与 item_ssr_bar.xml 一致
    // （6dp 歪的 marginStart + 26dp 歪 + 8dp 名字的 marginStart + 68dp 名字）。
    // 垫抽行用它对齐，保证不同行 / 不同内容的彩条长度只由抽数决定。
    private val BAR_RIGHT_OFFSET = 40
    private val BAR_RIGHT_W = 68

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        // 底部留出导航栏/手势安全区，避免最后一行内容或按钮被手势区压住
        findViewById<View>(R.id.main_root).applyBottomSafeInset()
        store = AccountStore(this)

        uidView = findViewById(R.id.uid_view)
        titleView = findViewById(R.id.title_view)
        heroRow = findViewById(R.id.hero_row)
        tagsRow = findViewById(R.id.tags_row)
        statsRow = findViewById(R.id.stats_row)
        poolStatView = findViewById(R.id.pool_stat_view)
        ssrList = findViewById(R.id.ssr_list)
        emptyView = findViewById(R.id.empty_view)
        footer = findViewById(R.id.footer_view)
        progress = findViewById(R.id.progress_bar)
        val tabLayout: TabLayout = findViewById(R.id.tab_layout)

        titleView.text = "尚无数据"
        renderFooter()

        for (pool in Gf2Api.POOLS) {
            tabLayout.addTab(tabLayout.newTab().setText(pool.name))
        }
        // 标签长按会弹一个纯白底的系统 tooltip（内容是标签名），跟暗金主题不搭，直接吃掉长按
        tabLayout.post { killTabTooltips(tabLayout) }
        tabLayout.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab) {
                current = Gf2Api.POOLS[tab.position]
                renderPool()
                // 选中态会让标签重新 update()，个别旧系统上会再挂回 tooltip，这里补一次
                tabLayout.post { killTabTooltips(tabLayout) }
            }

            override fun onTabUnselected(tab: TabLayout.Tab) {}

            override fun onTabReselected(tab: TabLayout.Tab) {}
        })
        tabLayout.getTabAt(Gf2Api.POOLS.indexOf(current))?.select()

        findViewById<Button>(R.id.add_button).setOnClickListener {
            startActivity(Intent(this, LoginActivity::class.java))
        }
        findViewById<Button>(R.id.account_button).setOnClickListener { showAccountManager() }
        findViewById<Button>(R.id.share_button).setOnClickListener { showShare() }
        findViewById<Button>(R.id.refresh_button).setOnClickListener { smartRefresh() }
        findViewById<Button>(R.id.update_button).setOnClickListener { checkUpdate(manual = true) }
        findViewById<Button>(R.id.announcement_button).setOnClickListener { checkAnnouncements(manual = true) }
        findViewById<Button>(R.id.community_button).setOnClickListener { openCommunity() }
        findViewById<Button>(R.id.export_key_button).setOnClickListener { showExportKey() }

        // 后台把五星表换成 R2 上的最新版，拿到后重算一次（表更新不用发版）
        lifecycleScope.launch {
            val table = withContext(Dispatchers.IO) { SsrTable.refresh(this@MainActivity) }
            tableSource = table.source
            renderFooter()
            reanalyzeFromCache()
        }
    }

    override fun onResume() {
        super.onResume()
        checkAnnouncements(manual = false)
        store.reload()
        if (store.isEmpty) {
            showEmptyState()
            return
        }
        applyCurrentAccount()
    }

    private fun openLogin() {
        startActivity(Intent(this, LoginActivity::class.java))
    }

    /** 绑定"当前账号"：换账号就立刻用它的缓存渲染，只有完全没缓存时才联网拉 */
    private fun applyCurrentAccount() {
        val account = store.current() ?: return
        renderAccountHeader(account)
        if (account.key == renderedUid) return
        renderedUid = account.key
        results.clear()
        if (account.hasRecords) {
            renderFromCache(account)
        } else if (account.token.isBlank()) {
            renderHeader()
            renderPool()
        } else {
            titleView.text = "正在查询…"
            fetchAndCache(account)
        }
        maybeAutoCheckUpdate()
    }

    /** 每次启动只在有账号之后静默检查一次更新（免得跟登录页叠在一起，也不会每次回前台都弹） */
    private fun maybeAutoCheckUpdate() {
        if (autoUpdateChecked || store.isEmpty) return
        autoUpdateChecked = true
        checkUpdate(manual = false)
    }

    private fun openCommunity() {
        val account = store.current() ?: run {
            showAddAccountPrompt()
            return
        }
        if (account.channel != GameChannel.OFFICIAL) {
            Toast.makeText(this, "B服账号暂不支持社区功能", Toast.LENGTH_SHORT).show()
            return
        }
        startActivity(Intent(this, CommunityActivity::class.java))
    }

    private fun renderAccountHeader(account: Account) {
        // 社区功能只对官服开放：B 服是 B 站登录，拿不到官方 access_token
        findViewById<Button>(R.id.community_button).visibility =
            if (account.channel == GameChannel.OFFICIAL) View.VISIBLE else View.GONE

        val parts = ArrayList<String>()
        parts.add(account.channel.label + " · UID: " + maskUid(account.uid))
        if (account.phone.isNotEmpty()) parts.add(maskPhone(account.phone))
        else if (account.email.isNotEmpty()) parts.add(maskEmail(account.email))
        if (account.recordsUpdatedAt > 0) {
            parts.add("更新 " + timeFormat.format(Date(account.recordsUpdatedAt * 1000)))
        }
        parts.add(if (account.token.isNotEmpty()) "凭证有效" else "凭证已过期")
        uidView.text = parts.joinToString(" · ")
    }

    private fun renderFromCache(account: Account) {
        results.clear()
        for (pool in Gf2Api.POOLS) {
            val raw = account.records[pool.typeId] ?: continue
            results[pool.typeId] = Gf2Api.analyzeCached(this, pool, raw)
        }
        renderHeader()
        renderPool()
    }

    /** 五星表更新后，用缓存重算一遍统计 */
    private fun reanalyzeFromCache() {
        val account = store.current() ?: return
        if (account.hasRecords) renderFromCache(account)
    }

    // ---------------------------------------------------------------- 刷新

    /** 刷新和导出共用续登流程，只有用户明确确认后才发验证码。 */
    private fun smartRefresh() {
        if (loading || exportKeyJob?.isActive == true || reauthBusy || reauthDialog?.isShowing == true) return
        val account = store.current() ?: run { showAddAccountPrompt(); return }
        if (account.token.isNotEmpty()) {
            fetchAndCache(account)
        } else {
            confirmReauthentication(account, PendingAction.REFRESH)
        }
    }

    private fun fetchAndCache(account: Account) {
        if (loading) return
        loading = true
        progress.visibility = View.VISIBLE
        if (results.isEmpty()) titleView.text = "正在查询…"
        lifecycleScope.launch {
            var ok = true
            try {
                val table = withContext(Dispatchers.IO) { SsrTable.refresh(this@MainActivity) }
                tableSource = table.source
                renderFooter()
                // 把本地已有记录交给接口层：拉回来的全量记录会与它按 fakeId 合并（历史只增不减）
                Gf2Api.fetchAllPools(this@MainActivity, account.token, account.records, account.channel) { result ->
                    store.putRecords(account.key, result.poolType, result.records)
                    if (store.current()?.key == account.key) {
                        results[result.poolType] = result
                        renderHeader()
                        if (current.typeId == result.poolType) renderPool()
                    }
                }
                if (store.current()?.key == account.key) {
                    renderHeader()
                    renderPool()
                    store.current()?.let { renderAccountHeader(it) }
                }
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                if (e is Gf2Exception && e.isTokenError) {
                    ok = false
                    val saved = store.accounts().find { it.key == account.key }
                    if (saved?.token == account.token) {
                        store.invalidateToken(account.key)
                        store.current()?.let { renderAccountHeader(it) }
                        confirmReauthentication(saved, PendingAction.REFRESH)
                    }
                } else {
                    handleError(e)
                }
            } finally {
                loading = false
                progress.visibility = View.GONE
                if (ok) store.save()
                if (results.isEmpty()) {
                    emptyView.text = if (store.current() == null) "请先点击「添加账号」并登录" else "暂无抽卡记录"
                    emptyView.visibility = View.VISIBLE
                } else {
                    emptyView.visibility = View.GONE
                }
            }
        }
    }

    private fun showAddAccountPrompt() {
        if (reauthDialog?.isShowing == true) return
        reauthDialog = MaterialAlertDialogBuilder(this)
            .setTitle("尚无数据")
            .setMessage("请先添加账号并登录。")
            .setPositiveButton("添加账号") { _, _ -> openLogin() }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun confirmReauthentication(account: Account, action: PendingAction) {
        if (store.current()?.key != account.key || reauthBusy || reauthDialog?.isShowing == true) return
        if (account.phone.length != 11) {
            // 邮箱账号没有手机号，发不了验证码：回登录页并预填邮箱，用密码续登
            startActivity(
                Intent(this, LoginActivity::class.java)
                    .putExtra(LoginActivity.EXTRA_CHANNEL, account.channel.id)
                    .putExtra(LoginActivity.EXTRA_ACCOUNT, account.email)
            )
            return
        }
        reauthDialog = MaterialAlertDialogBuilder(this)
            .setTitle("登录已过期")
            .setMessage("是否向 " + maskPhone(account.phone) + " 发送验证码？")
            .setPositiveButton("发送验证码") { _, _ -> sendCode(account, action) }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun sendCode(account: Account, action: PendingAction) {
        if (reauthBusy || store.current()?.key != account.key) return
        reauthBusy = true
        lifecycleScope.launch {
            try {
                val challenge = Gf2Api.sendSmsCode(this@MainActivity, account.phone, account.channel)
                if (store.current()?.key == account.key) showCodeDialog(account, action, challenge)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                toast("验证码发送失败：" + (e.message ?: "请重试"))
            } finally {
                reauthBusy = false
            }
        }
    }

    private fun showCodeDialog(account: Account, action: PendingAction, challenge: SmsChallenge) {
        val input = EditText(this)
        input.inputType = InputType.TYPE_CLASS_NUMBER
        input.hint = "6 位验证码"
        input.filters = arrayOf<InputFilter>(InputFilter.LengthFilter(6))
        input.setBackgroundResource(R.drawable.bg_input)
        input.setTextColor(color(R.color.text))
        input.setHintTextColor(color(R.color.text_dim))
        input.setPadding(dp(14), dp(12), dp(14), dp(12))
        val container = FrameLayout(this)
        val pad = dp(20)
        container.setPadding(pad, dp(6), pad, 0)
        container.addView(
            input,
            FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        )
        val dialog = MaterialAlertDialogBuilder(this)
            .setTitle("验证码登录")
            .setMessage("验证码已发送至 " + maskPhone(account.phone))
            .setView(container)
            .setPositiveButton("登录", null)
            .setNegativeButton("取消", null)
            .create()
        reauthDialog = dialog
        dialog.show()
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
            val code = input.text.toString().trim()
            if (code.length != 6) {
                input.error = "请输入 6 位验证码"
            } else {
                dialog.dismiss()
                loginWithCode(account, code, action, challenge)
            }
        }
    }

    private fun loginWithCode(account: Account, code: String, action: PendingAction, challenge: SmsChallenge) {
        if (code.length != 6) {
            toast("请输入 6 位验证码")
            return
        }
        if (reauthBusy || store.current()?.key != account.key) return
        reauthBusy = true
        progress.visibility = View.VISIBLE
        lifecycleScope.launch {
            try {
                val result = Gf2Api.smsLogin(this@MainActivity, account.phone, code, account.channel, challenge)
                if (store.current()?.key != account.key) return@launch
                if (result.uid != account.uid) {
                    toast("登录账号不一致，请重新添加账号")
                    return@launch
                }
                store.upsert(result.uid, account.phone, result.accessToken, account.channel)
                store.reload()
                val renewed = store.current() ?: return@launch
                renderAccountHeader(renewed)
                // 先释放续登锁，再恢复用户原先选择的操作，避免额外刷新或重复发码。
                reauthBusy = false
                when (action) {
                    PendingAction.REFRESH -> fetchAndCache(renewed)
                    PendingAction.EXPORT -> showExportKey()
                }
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                toast("登录失败：" + (e.message ?: "请重试"))
            } finally {
                reauthBusy = false
                if (!loading) progress.visibility = View.GONE
            }
        }
    }

    // ------------------------------------------------------------ 选择账号

    /** 管理账号：点一行=切换账号；行尾「删除」=删掉该账号（二次确认） */
    private fun showAccountManager() {
        if (store.isEmpty) {
            toast("还没有账号，请先「添加账号」")
            return
        }
        val list = store.accounts()
        val currentUid = store.currentUid
        var dialog: AlertDialog? = null

        val adapter = object : BaseAdapter() {
            override fun getCount(): Int = list.size
            override fun getItem(position: Int): Any = list[position]
            override fun getItemId(position: Int): Long = position.toLong()

            override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
                val view = convertView
                    ?: layoutInflater.inflate(R.layout.item_account_dialog, parent, false)
                val account = list[position]
                val isCurrent = account.key == currentUid

                val mark = view.findViewById<TextView>(R.id.acc_mark)
                val uid = view.findViewById<TextView>(R.id.acc_uid)
                val sub = view.findViewById<TextView>(R.id.acc_sub)
                val records = view.findViewById<TextView>(R.id.acc_records)

                mark.text = if (isCurrent) "●" else "○"
                mark.setTextColor(color(if (isCurrent) R.color.gold else R.color.text_dim))
                uid.text = maskUid(account.uid)
                uid.setTextColor(color(if (isCurrent) R.color.gold else R.color.text))

                val bits = ArrayList<String>()
                bits.add(account.channel.label)
                if (account.phone.isNotEmpty()) bits.add(maskPhone(account.phone))
                else if (account.email.isNotEmpty()) bits.add(maskEmail(account.email))
                bits.add(if (account.token.isNotEmpty()) "凭证有效" else "凭证已过期")
                if (account.recordsUpdatedAt > 0) {
                    bits.add("更新 " + timeFormat.format(Date(account.recordsUpdatedAt * 1000)))
                }
                sub.text = bits.joinToString(" · ")
                records.text = recordCountText(account)

                view.findViewById<TextView>(R.id.acc_delete).setOnClickListener {
                    confirmDelete(account) {
                        dialog?.dismiss()
                        afterAccountsChanged()
                    }
                }
                return view
            }
        }

        dialog = MaterialAlertDialogBuilder(this)
            .setTitle("管理账号")
            .setAdapter(adapter) { _, which ->
                val account = list[which]
                if (account.key != store.currentUid) {
                    store.select(account.key)
                    renderedUid = null
                    applyCurrentAccount()
                }
            }
            .setPositiveButton("添加账号") { _, _ -> startActivity(Intent(this, LoginActivity::class.java)) }
            .setNegativeButton("关闭", null)
            .show()
    }

    private fun recordCountText(account: Account): String {
        var total = 0
        for (records in account.records.values) total += records.size
        return if (total == 0) "无记录" else "$total 条"
    }

    private fun confirmDelete(account: Account, onDeleted: () -> Unit) {
        MaterialAlertDialogBuilder(this)
            .setTitle("删除账号")
            .setMessage(
                "确定删除 " + maskUid(account.uid) + " 吗？\n本机保存的登录凭证和 "
                    + recordCountText(account) + "记录都会被清掉，无法恢复。"
            )
            .setPositiveButton("删除") { _, _ ->
                store.remove(account.key)
                toast("已删除 " + maskUid(account.uid))
                onDeleted()
            }
            .setNegativeButton("取消", null)
            .show()
    }

    /** 账号被删/切换后重新绑定界面；一个账号都不剩时回到空态 */
    private fun afterAccountsChanged() {
        if (store.isEmpty) {
            showEmptyState()
            return
        }
        val account = store.current()
        if (account == null) {
            showEmptyState()
            return
        }
        if (account.key == renderedUid) {
            renderAccountHeader(account)
        } else {
            renderedUid = null
            applyCurrentAccount()
        }
    }

    private fun showEmptyState() {
        renderedUid = null
        results.clear()
        uidView.text = "还没有账号"
        titleView.text = "尚无数据"
        heroRow.removeAllViews()
        tagsRow.removeAllViews()
        statsRow.removeAllViews()
        ssrList.removeAllViews()
        poolStatView.text = ""
        emptyView.text = "请先点击「添加账号」并登录"
        emptyView.visibility = View.VISIBLE
    }

    // ---------------------------------------------------------------- 渲染

    private fun renderHeader() {
        val pools = results.values
        if (pools.isEmpty()) return
        val total = pools.sumOf { it.total }
        val ssr = pools.sumOf { it.ssrCount }
        titleView.text = Titles.title(total, ssr)

        val average = if (ssr == 0) "—" else Math.round(total.toFloat() / ssr).toString() + " 抽"

        val limited = listOf(
            Gf2Api.POOL_CHARACTER, Gf2Api.POOL_WEAPON,
            Gf2Api.POOL_CUSTOM_CHARACTER, Gf2Api.POOL_CUSTOM_WEAPON
        )
        val limitedSsr = limited.sumOf { results[it]?.ssrCount ?: 0 }
        val limitedWai = limited.sumOf { results[it]?.waiCount ?: 0 }
        val notWai = if (limitedSsr == 0) "—"
        else String.format(Locale.US, "%.1f%%", (limitedSsr - limitedWai) * 100.0 / limitedSsr)

        heroRow.removeAllViews()
        addColumn(heroRow, "$total 抽", getString(R.string.main_total), 24f)
        addColumn(heroRow, average, getString(R.string.main_average), 24f)
        addColumn(heroRow, notWai, getString(R.string.main_not_wai), 24f)

        val pity = pools.maxOfOrNull { it.pity } ?: 0
        val maxCost = pools.maxOfOrNull { it.maxCost } ?: 0
        renderTags(Titles.tags(total, ssr, pity, maxCost))
        renderStats(ssr)
    }

    private fun renderTags(tags: List<String>) {
        tagsRow.removeAllViews()
        for (tag in tags) {
            val view = TextView(this)
            view.text = tag
            view.textSize = 12f
            view.setTextColor(color(R.color.gold))
            view.setBackgroundResource(R.drawable.bg_pill)
            view.setPadding(dp(12), dp(6), dp(12), dp(6))
            val params = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
            params.marginEnd = dp(8)
            view.layoutParams = params
            tagsRow.addView(view)
        }
    }

    private fun renderStats(ssrCount: Int) {
        statsRow.removeAllViews()
        addColumn(statsRow, ssrCount.toString(), "五星数", 20f)
        addColumn(statsRow, averageOf(intArrayOf(3, 6)), "角色平均", 20f)
        addColumn(statsRow, averageOf(intArrayOf(4, 7)), "武器平均", 20f)
        addColumn(statsRow, averageOf(intArrayOf(1)), "常驻平均", 20f)
    }

    private fun averageOf(types: IntArray): String {
        var total = 0
        var ssr = 0
        for (type in types) {
            val result = results[type] ?: continue
            total += result.total
            ssr += result.ssrCount
        }
        return if (ssr == 0) "—" else Math.round(total.toFloat() / ssr).toString() + "抽"
    }

    private fun addColumn(row: LinearLayout, value: String, label: String, valueSize: Float) {
        val column = LinearLayout(this)
        column.orientation = LinearLayout.VERTICAL
        column.layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)

        val valueView = TextView(this)
        valueView.text = value
        valueView.textSize = valueSize
        valueView.typeface = Typeface.DEFAULT_BOLD
        valueView.setTextColor(color(R.color.gold_bright))
        valueView.gravity = Gravity.CENTER

        val labelView = TextView(this)
        labelView.text = label
        labelView.textSize = 11f
        labelView.setTextColor(color(R.color.text_dim))
        labelView.gravity = Gravity.CENTER

        column.addView(valueView)
        column.addView(labelView)
        row.addView(column)
    }

    /**
     * 干掉 TabLayout 标签长按弹出的系统 tooltip（纯白底 + 标签名，跟暗金主题不搭）。
     * 只清 tooltip 文案，不碰点击/长按监听。
     */
    private fun killTabTooltips(view: View) {
        TooltipCompat.setTooltipText(view, null)
        if (view is ViewGroup) {
            for (i in 0 until view.childCount) killTabTooltips(view.getChildAt(i))
        }
    }

    private fun renderPool() {
        val result = results[current.typeId]
        ssrList.removeAllViews()
        if (result == null) {
            poolStatView.text = current.name + "：暂无数据"
            return
        }
        poolStatView.text = current.name + " · 共 " + result.total + " 抽 · 五星 " + result.ssrCount +
            " 个 · 歪 " + result.waiCount + " 个 · 当前垫 " + result.pity + " 抽"
        ssrList.addView(pityRow(result))
        val hits = result.ssrHits.sortedByDescending { it.time }
        if (hits.isEmpty()) {
            emptyView.text = "这个池子还没出过五星"
            emptyView.visibility = View.VISIBLE
            return
        }
        emptyView.visibility = View.GONE
        for (hit in hits) ssrList.addView(barRow(hit))
    }

    private fun pityRow(result: PoolResult): View {
        val row = LinearLayout(this)
        row.orientation = LinearLayout.HORIZONTAL
        row.gravity = Gravity.CENTER_VERTICAL
        row.setPadding(0, dp(4), 0, dp(10))

        val badge = TextView(this)
        badge.text = "?"
        badge.gravity = Gravity.CENTER
        badge.textSize = 14f
        badge.setTextColor(color(R.color.gold))
        badge.background = rounded(color(R.color.pill), 18)
        row.addView(badge, LinearLayout.LayoutParams(dp(36), dp(36)))

        // 垫抽数：放在和五星行「抽数」同一列的位置（问号右边）
        val cost = TextView(this)
        cost.text = result.pity.toString()
        cost.gravity = Gravity.CENTER
        cost.textSize = 15f
        cost.typeface = Typeface.DEFAULT_BOLD
        cost.setTextColor(color(R.color.gold))
        row.addView(cost, LinearLayout.LayoutParams(dp(44), ViewGroup.LayoutParams.WRAP_CONTENT))

        val track = LinearLayout(this)
        track.orientation = LinearLayout.HORIZONTAL
        val bar = View(this)
        val rest = View(this)
        val fraction = (result.pity.toFloat() / Titles.HARD_PITY).coerceIn(0f, 1f)
        bar.background = stripe(color(R.color.bar_gold), color(R.color.bar_gold_light))
        track.addView(bar, LinearLayout.LayoutParams(0, dp(22), fraction))
        track.addView(rest, LinearLayout.LayoutParams(0, dp(22), 1f - fraction))
        row.addView(track, LinearLayout.LayoutParams(0, dp(22), 1f))

        // 最右边保留「已垫 N 抽」（不写保底）；槽位与五星行的「歪 + 名字」完全一致，
        // 这样垫抽行的条长和五星行的条长对得上，不会一行长一行短。
        val label = TextView(this)
        label.text = "已垫 " + result.pity + " 抽"
        label.setTextColor(color(R.color.gold))
        label.textSize = 12f
        label.gravity = Gravity.CENTER_VERTICAL
        row.addView(
            label,
            LinearLayout.LayoutParams(dp(BAR_RIGHT_W), ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                marginStart = dp(BAR_RIGHT_OFFSET)
            }
        )
        return row
    }

    /** 一行五星。武器按"物品 id"判定（常驻池里人形和武器是混在一起的，不能看池子） */
    private fun barRow(hit: SsrHit): View {
        val row = layoutInflater.inflate(R.layout.item_ssr_bar, ssrList, false)
        val avatar = row.findViewById<ImageView>(R.id.ssr_avatar)
        val avatarText = row.findViewById<TextView>(R.id.ssr_avatar_text)
        val cost = row.findViewById<TextView>(R.id.ssr_cost)
        val bar = row.findViewById<View>(R.id.ssr_bar)
        val rest = row.findViewById<View>(R.id.ssr_bar_rest)
        val name = row.findViewById<TextView>(R.id.ssr_name)
        val waiTag = row.findViewById<TextView>(R.id.ssr_wai)

        val baseRes = when {
            hit.costDraws < 30 -> R.color.bar_green
            hit.costDraws < 60 -> R.color.bar_yellow
            else -> R.color.bar_red
        }
        val lightRes = when (baseRes) {
            R.color.bar_green -> R.color.bar_green_light
            R.color.bar_yellow -> R.color.bar_yellow_light
            else -> R.color.bar_red_light
        }
        // 条用深色（照例图），数字用同档位的亮色（黑底上要看得清）
        val textRes = when (baseRes) {
            R.color.bar_green -> R.color.bar_green_text
            R.color.bar_yellow -> R.color.bar_yellow_text
            else -> R.color.bar_red_text
        }
        val barColor = color(baseRes)
        val fraction = (hit.costDraws.toFloat() / Titles.HARD_PITY).coerceIn(0.05f, 1f)

        bar.background = stripe(barColor, color(lightRes))
        val barParams = bar.layoutParams as LinearLayout.LayoutParams
        barParams.weight = fraction
        bar.layoutParams = barParams
        val restParams = rest.layoutParams as LinearLayout.LayoutParams
        restParams.weight = 1f - fraction
        rest.layoutParams = restParams

        cost.text = hit.costDraws.toString()
        cost.setTextColor(color(textRes))
        name.text = hit.name
        waiTag.visibility = if (hit.isWai) View.VISIBLE else View.INVISIBLE

        val weapon = SsrTable.get(this).isWeaponItem(hit.itemId)
        avatar.visibility = View.VISIBLE
        avatarText.visibility = View.GONE
        if (weapon) {
            avatar.scaleType = ImageView.ScaleType.FIT_CENTER
            avatar.load(Gf2Api.WEAPON_IMAGE_BASE + hit.itemId + ".png") {
                listener(onError = { _, _ ->
                    avatar.visibility = View.GONE
                    avatarText.visibility = View.VISIBLE
                    avatarText.text = "武"
                })
            }
        } else {
            avatar.scaleType = ImageView.ScaleType.CENTER_CROP
            avatar.load(Gf2Api.IMAGE_BASE + hit.itemId + ".png")
        }
        return row
    }

    private fun handleError(e: Exception) {
        val message = describe(e)
        if (results.isEmpty()) titleView.text = "查询失败"
        emptyView.text = message
        emptyView.visibility = View.VISIBLE
        toast(message)
    }

    private fun describe(e: Exception): String =
        if (e is Gf2Exception) e.message ?: ("code=" + e.code) else (e.message ?: e.javaClass.simpleName)

    // ---------------------------------------------------------------- 公告

    /**
     * 自动检查：App 打开/回到前台时检查一次，打开期间不做定时轮询。
     * 用户点「公告」时 manual=true，强制拿最新清单；网络失败时回退到本机持久化缓存。
     */
    private fun checkAnnouncements(manual: Boolean) {
        if (announcementJob?.isActive == true) {
            if (manual) toast("正在获取公告…")
            return
        }

        announcementJob = lifecycleScope.launch {
            when (val result = AnnouncementCenter.fetch(this@MainActivity, force = manual)) {
                is AnnouncementCenter.FetchResult.Success -> {
                    val latest = AnnouncementCenter.mostRecent(result.feed)
                    currentAnnouncement = latest
                    updateAnnouncementButton()
                    if (latest != null && (manual || AnnouncementCenter.isUnread(this@MainActivity, latest.id))) {
                        showAnnouncement(latest)
                    } else if (manual) {
                        toast(getString(R.string.announcement_empty))
                    }
                }

                is AnnouncementCenter.FetchResult.Failed -> {
                    val cached = currentAnnouncement
                    if (manual && cached != null) {
                        showAnnouncement(cached)
                    } else if (manual) {
                        toast(getString(R.string.announcement_fetch_failed, result.message))
                    }
                }
            }
        }
    }

    private fun updateAnnouncementButton() {
        val button = findViewById<Button>(R.id.announcement_button)
        val announcement = currentAnnouncement
        button.text = if (announcement != null && AnnouncementCenter.isUnread(this, announcement.id)) {
            getString(R.string.main_announcement_new)
        } else {
            getString(R.string.main_announcement)
        }
    }

    private fun showAnnouncement(announcement: AnnouncementCenter.Announcement) {
        val view = layoutInflater.inflate(R.layout.dialog_announcement, null)
        val content = view.findViewById<LinearLayout>(R.id.announcement_content)
        val meta = view.findViewById<TextView>(R.id.announcement_meta)
        val body = view.findViewById<TextView>(R.id.announcement_body)

        meta.text = if (announcement.publishedAt > 0L) {
            "公告 · " + announcementTimeFormat.format(Date(announcement.publishedAt * 1000L))
        } else {
            "公告"
        }
        body.text = announcement.body
        body.visibility = if (announcement.body.isBlank()) View.GONE else View.VISIBLE

        announcement.images.take(MAX_ANNOUNCEMENT_IMAGES).forEachIndexed { index, rawUrl ->
            val image = AspectRatioImageView(this)
            val params = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { topMargin = dp(12) }
            image.layoutParams = params
            image.adjustViewBounds = true
            image.scaleType = ImageView.ScaleType.FIT_CENTER
            image.contentDescription = getString(R.string.announcement_image, index + 1)
            image.load(AnnouncementCenter.imageUrl(rawUrl)) {
                error(R.color.card)
            }
            content.addView(image)
        }

        announcementDialog?.dismiss()
        announcementDialog = MaterialAlertDialogBuilder(this)
            .setTitle(announcement.title)
            .setView(view)
            .setPositiveButton(getString(R.string.announcement_dismiss), null)
            .create()
        announcementDialog?.show()

        currentAnnouncement = announcement
        AnnouncementCenter.markSeen(this, announcement.id)
        updateAnnouncementButton()
    }

    // ---------------------------------------------------------------- 更新

    /** 底部说明行 */
    private fun renderFooter() {
        var text = getString(R.string.main_footer)
        if (tableSource != null) text += " · 五星表：" + tableSource
        footer.text = text
    }

    /** 有新版但用户点了「稍后」时，把按钮文字改成「有新版本 x.y.z」，免得错过 */
    private fun markUpdatePending(version: String?) {
        val button = findViewById<Button>(R.id.update_button)
        button.text = if (version == null) getString(R.string.main_check_update) else "有新版本 " + version
    }

    /** 检查更新。manual=false 时全静默（启动后自动跑一次）；manual=true 是用户点了底部那行 */
    private fun checkUpdate(manual: Boolean) {
        if (updateJob?.isActive == true) return
        updateJob = lifecycleScope.launch {
            if (manual) toast("正在检查更新…")
            when (val result = UpdateChecker.check(this@MainActivity)) {
                is UpdateChecker.Result.Newer -> {
                    markUpdatePending(result.update.version)
                    showUpdateDialog(result.local, result.update)
                }
                is UpdateChecker.Result.Latest -> {
                    markUpdatePending(null)
                    if (manual) toast("已是最新版本 " + result.local)
                }
                is UpdateChecker.Result.Failed -> if (manual) toast("检查更新失败：" + result.message)
            }
        }
    }

    /** 有新版：先说清楚「从哪个版本到哪个版本、多大、改了什么」，再让用户决定 */
    private fun showUpdateDialog(local: String, update: UpdateChecker.Update) {
        val size = if (update.size > 0) String.format(Locale.US, "（%.1f MB）", update.size / 1048576.0) else ""
        val body = StringBuilder("当前版本 " + local + " → 新版本 " + update.version).append(size)
        if (update.info.isNotBlank()) body.append("\n\n").append(update.info.trim())
        body.append("\n\n安装交给系统安装器；签名不一致系统会自己拒绝，装不坏现在这个版本。")
        MaterialAlertDialogBuilder(this)
            .setTitle("发现新版本 " + update.version)
            .setMessage(body.toString())
            .setPositiveButton("立即更新") { _, _ -> startUpdate(update) }
            .setNegativeButton("稍后", null)
            .show()
    }

    private fun startUpdate(update: UpdateChecker.Update) {
        // 系统要先允许「安装未知应用」，否则下完了也拉不起安装器
        if (UpdateChecker.needInstallPermission(this)) {
            MaterialAlertDialogBuilder(this)
                .setTitle("先允许安装应用")
                .setMessage(
                    "系统要求先允许「" + getString(R.string.app_name) + "」安装未知来源的应用。\n\n" +
                        "点「去设置」打开开关，回来再点一次「立即更新」——安装包会缓存在本机，不会重复下载。"
                )
                .setPositiveButton("去设置") { _, _ -> UpdateChecker.openInstallPermissionSettings(this) }
                .setNegativeButton("取消", null)
                .show()
            return
        }

        val view = layoutInflater.inflate(R.layout.dialog_update_progress, null)
        val bar = view.findViewById<ProgressBar>(R.id.update_progress)
        val label = view.findViewById<TextView>(R.id.update_text)
        label.text = "正在下载 " + update.version + " …"
        val dialog = MaterialAlertDialogBuilder(this)
            .setTitle("正在更新")
            .setView(view)
            .setNegativeButton("取消", null)
            .setCancelable(false)
            .create()
        dialog.show()
        dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setOnClickListener {
            downloadJob?.cancel()
            dialog.dismiss()
            toast("已取消更新")
        }

        downloadJob = lifecycleScope.launch {
            try {
                val apk = withContext(Dispatchers.IO) {
                    UpdateChecker.download(this@MainActivity, update) { percent ->
                        runOnUiThread {
                            bar.progress = percent
                            label.text = "正在下载 " + update.version + " … " + percent + "%"
                        }
                    }
                }
                dialog.dismiss()
                toast("下载完成，正在打开安装器…")
                UpdateChecker.install(this@MainActivity, apk)
            } catch (e: CancellationException) {
                // 用户自己点的取消，不用报错
            } catch (e: Exception) {
                dialog.dismiss()
                toast("更新失败：" + (e.message ?: e.javaClass.simpleName))
            }
        }
    }

    // ---------------------------------------------------------------- 小程序导入钥匙

    /** 点「导出到小程序」立刻核验凭证：过期就先续登，核验通过才弹说明框。 */
    private fun showExportKey() {
        if (loading || exportKeyJob?.isActive == true || reauthBusy || reauthDialog?.isShowing == true) return
        val account = store.current() ?: run { showAddAccountPrompt(); return }
        if (account.token.isBlank()) {
            confirmReauthentication(account, PendingAction.EXPORT)
            return
        }
        // 固定本次导出的账号与凭证，核验中切换账号时不能把旧钥匙复制出去。
        verifyExportAccount(account.uid, account.token, account.channel)
    }

    /**
     * 导出前的核验：先按「刷新」同一条记录接口确认凭证真的没过期（账号接口对过期凭证
     * 也会返回 uid，不能当过期检查），再核对钥匙里的 uid 与凭证是否同一个账号。
     * 过期时与刷新共用续登确认；通过后才弹说明框，框里的「复制」不再发请求。
     */
    private fun verifyExportAccount(uid: String, token: String, channel: GameChannel) {
        if (exportKeyJob?.isActive == true) return
        val button = findViewById<Button>(R.id.export_key_button)
        button.isEnabled = false
        button.setText(R.string.export_key_checking)
        exportKeyJob = lifecycleScope.launch {
            try {
                // 在发请求前校验格式；错误内容不回显凭证。
                MiniProgramKey.encode(uid, token, channel)
                Gf2Api.verifyCredential(token, channel)
                // B服游戏令牌不被官方 account/info 接受；渠道 6 的记录接口已证明凭证有效，
                // UID 来自本次 B站登录结果并随账号存储，不再调用官服专用 UID 接口。
                if (channel != GameChannel.BILIBILI) {
                    val officialUid = Gf2Api.fetchAccountUid(token, channel)
                    if (officialUid != uid) {
                        toast(getString(R.string.export_key_uid_mismatch))
                        return@launch
                    }
                }
                if (matchingAccount(uid, token, channel) == null) {
                    toast(getString(R.string.export_key_account_changed))
                    return@launch
                }
                showExportKeyDialog(uid, token, channel)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // 只记录异常类型与接口文案，不记录钥匙或凭证。
                Log.w("XKL", "export verification failed: " + e.javaClass.simpleName + ": " + describe(e).take(240))
                // 凭证过期与刷新使用同一套续登确认，不跳转登录页、不自动发码。
                val selected = matchingAccount(uid, token, channel)
                if (e is Gf2Exception && e.isTokenError && selected != null) {
                    store.invalidateToken(selected.key)
                    store.reload()
                    store.current()?.let {
                        renderAccountHeader(it)
                        confirmReauthentication(it, PendingAction.EXPORT)
                    }
                } else {
                    toast(getString(R.string.export_key_failed))
                }
            } finally {
                button.isEnabled = true
                button.setText(R.string.main_export_key)
            }
        }
    }

    /** 核验期间账号或凭证变了就不再继续，避免把上一个账号的钥匙发出去。 */
    private fun matchingAccount(uid: String, token: String, channel: GameChannel): Account? {
        val selected = store.current() ?: return null
        return if (selected.uid == uid && selected.channel == channel && selected.token == token) selected else null
    }

    /** 凭证已核验通过的说明框：只负责确认，不再发网络请求。 */
    private fun showExportKeyDialog(uid: String, token: String, channel: GameChannel) {
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.export_key_title)
            .setMessage(getString(R.string.export_key_explanation, maskUid(uid)))
            .setPositiveButton(R.string.export_key_copy) { _, _ -> copyMiniProgramKey(uid, token, channel) }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun copyMiniProgramKey(uid: String, token: String, channel: GameChannel) {
        if (matchingAccount(uid, token, channel) == null) {
            toast(getString(R.string.export_key_account_changed))
            return
        }
        val clipboard = getSystemService(CLIPBOARD_SERVICE) as? ClipboardManager
        if (clipboard == null) {
            toast(getString(R.string.export_key_copy_failed))
            return
        }
        try {
            clipboard.setPrimaryClip(MiniProgramKey.clip(MiniProgramKey.encode(uid, token, channel)))
            toast(getString(R.string.export_key_copied))
        } catch (e: Exception) {
            // 凭据格式在核验时已经校验过；这里只可能是账号数据被外部改坏或系统拒绝写剪贴板。
            toast(getString(R.string.export_key_copy_failed))
        }
    }

    // ---------------------------------------------------------------- 分享

    /** 分享：直接出「当前卡池」的竖版长图（暗金 App 风格；要发别的池就切过去再分享） */
    private fun showShare() {
        val pool = current
        val result = results[pool.typeId]
        if (result == null || result.total == 0) {
            toast("当前卡池没有数据，先点「刷新」或切到别的卡池")
            return
        }
        progress.visibility = View.VISIBLE
        toast("正在生成分享图…")
        lifecycleScope.launch {
            try {
                val bitmap = withContext(Dispatchers.IO) {
                    ShareCard.render(this@MainActivity, results.values, pool, result)
                }
                val uri = withContext(Dispatchers.IO) { saveShareFile(bitmap) }
                showShareActions(bitmap, uri)
            } catch (e: Exception) {
                toast("生成失败：" + describe(e))
            } finally {
                progress.visibility = View.GONE
            }
        }
    }

    private fun saveShareFile(bitmap: Bitmap): Uri {
        val dir = File(cacheDir, "share")
        if (!dir.exists()) dir.mkdirs()
        val file = File(dir, "gf2gacha_share.png")
        FileOutputStream(file).use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        return FileProvider.getUriForFile(this, packageName + ".files", file)
    }

    /** 出图后：分享到微信 / 分享到 QQ / 保存图片 / 更多分享（跟企业级软件一个路子） */
    private fun showShareActions(bitmap: Bitmap, uri: Uri) {
        val view = layoutInflater.inflate(R.layout.dialog_share_actions, null)
        view.findViewById<ImageView>(R.id.share_preview).setImageBitmap(bitmap)
        val dialog = MaterialAlertDialogBuilder(this)
            .setTitle(R.string.share_done_title)
            .setView(view)
            .setNegativeButton("关闭", null)
            .create()
        view.findViewById<Button>(R.id.share_wechat).setOnClickListener {
            shareImage(uri, "com.tencent.mm", "微信")
        }
        view.findViewById<Button>(R.id.share_qq).setOnClickListener {
            shareImage(uri, "com.tencent.mobileqq", "QQ")
        }
        view.findViewById<Button>(R.id.share_save).setOnClickListener { saveToGallery(bitmap) }
        view.findViewById<Button>(R.id.share_more).setOnClickListener { shareImage(uri, null, null) }
        dialog.show()
    }

    private fun shareImage(uri: Uri, pkg: String?, appName: String?) {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "image/png"
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        if (pkg != null) intent.setPackage(pkg)
        try {
            startActivity(intent)
        } catch (e: ActivityNotFoundException) {
            if (pkg != null) {
                toast("没找到" + appName + "，改用系统分享")
                shareImage(uri, null, null)
            } else {
                toast("没有可用的分享应用")
            }
        }
    }

    private fun saveToGallery(bitmap: Bitmap) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            pendingSave = bitmap
            requestPermissions(arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE), REQ_STORAGE)
            return
        }
        val name = "gf2gacha_" + SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date()) + ".png"
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val values = ContentValues().apply {
                    put(MediaStore.Images.Media.DISPLAY_NAME, name)
                    put(MediaStore.Images.Media.MIME_TYPE, "image/png")
                    put(
                        MediaStore.Images.Media.RELATIVE_PATH,
                        Environment.DIRECTORY_PICTURES + "/夏克里助手"
                    )
                    put(MediaStore.Images.Media.IS_PENDING, 1)
                }
                val target = contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
                    ?: throw IllegalStateException("MediaStore 插入失败")
                contentResolver.openOutputStream(target)?.use {
                    bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)
                }
                values.clear()
                values.put(MediaStore.Images.Media.IS_PENDING, 0)
                contentResolver.update(target, values, null, null)
                toast("已保存到相册：Pictures/夏克里助手")
            } else {
                val dir = File(
                    Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES),
                    "夏克里助手"
                )
                if (!dir.exists()) dir.mkdirs()
                val file = File(dir, name)
                FileOutputStream(file).use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
                MediaScannerConnection.scanFile(this, arrayOf(file.absolutePath), arrayOf("image/png"), null)
                toast("已保存到相册：Pictures/夏克里助手")
            }
        } catch (e: Exception) {
            toast("保存失败：" + describe(e))
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_STORAGE) {
            val bitmap = pendingSave
            pendingSave = null
            if (bitmap == null) return
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                saveToGallery(bitmap)
            } else {
                toast("没有存储权限，无法保存到相册")
            }
        }
    }

    /**
     * 斜条纹彩条（例图那种：深底 + 同色系浅条，持续向右移动）。
     * 几何按例图实测标定：斜条宽 : 间距 ≈ 17 : 14，dx/dy ≈ 0.8，方向 "\"。
     */
    private fun stripe(base: Int, stripeColor: Int): StripeDrawable = StripeDrawable(
        baseColor = base,
        stripeColor = stripeColor,
        // 加粗 + 拉开间隔：周期 15dp -> 32dp（≈1.45 倍条高，与例图 38px/26px 一致）
        stripeWidth = dp(15).toFloat(),
        gapWidth = dp(17).toFloat(),
        slope = 0.8f,
        cornerRadius = dp(6).toFloat(),
        // 速度 = 周期 / 时长 = 32dp / 1800ms ≈ 17.8 dp/s
        // （上一版周期拉到 32dp 但时长没动，等于速度翻倍，看着太快）
        durationMs = 1800L
    )

    private fun rounded(colorValue: Int, radiusDp: Int): GradientDrawable {
        val drawable = GradientDrawable()
        drawable.shape = GradientDrawable.RECTANGLE
        drawable.cornerRadius = dp(radiusDp).toFloat()
        drawable.setColor(colorValue)
        return drawable
    }

    private fun maskUid(uid: String): String =
        if (uid.length <= 6) uid else uid.take(3) + "****" + uid.takeLast(3)

    private fun maskPhone(phone: String): String =
        if (phone.length != 11) phone else phone.take(3) + "****" + phone.takeLast(4)

    /** 邮箱打码：保留前 2 位和完整域名（12***@qq.com） */
    private fun maskEmail(email: String): String {
        val at = email.indexOf('@')
        if (at <= 0) return email
        val name = email.substring(0, at)
        val head = if (name.length <= 2) name.take(1) else name.take(2)
        return head + "***" + email.substring(at)
    }

    private fun toast(text: String) {
        Toast.makeText(this, text, Toast.LENGTH_SHORT).show()
    }

    private fun color(id: Int): Int = ContextCompat.getColor(this, id)

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private companion object {
        const val REQ_STORAGE = 1001
        const val MAX_ANNOUNCEMENT_IMAGES = 6
        val announcementTimeFormat = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault())
        val timeFormat = SimpleDateFormat("MM-dd HH:mm", Locale.getDefault())
    }
}
