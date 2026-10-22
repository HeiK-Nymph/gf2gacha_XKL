package uk.gf2gacha.xkl.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** 一个已保存的账号：登录凭证 + 抽卡记录缓存（两者都只在本机） */
class Account(val uid: String, val channel: GameChannel = GameChannel.OFFICIAL) {
    val key: String get() = channel.accountKey(uid)
    var phone: String = ""
    var token: String = ""
    var tokenSavedAt: Long = 0L
    var recordsUpdatedAt: Long = 0L

    /** poolType -> 原始记录，用于离线查看、切换账号时立刻渲染 */
    val records = LinkedHashMap<Int, List<GachaRecord>>()

    val hasRecords: Boolean get() = records.isNotEmpty()
}

/**
 * 多账号本地存储（files/accounts.json）。
 *
 * 关键设计：**切账号只切"当前账号"，不清任何账号的凭证和记录**。
 * 每个账号各自保存 token 和五池记录，所以：
 *   - 切到别的账号，直接用它自己的缓存渲染，不用重新登录
 *   - 切回来，token 还在，可以直接刷新
 */
class AccountStore(context: Context) {

    private val file = File(context.filesDir, "accounts.json")
    private val items = LinkedHashMap<String, Account>()

    var currentUid: String? = null
        private set

    init {
        reload()
    }

    val isEmpty: Boolean get() = items.isEmpty()

    fun accounts(): List<Account> = items.values.toList()

    fun current(): Account? = currentUid?.let { items[it] } ?: items.values.firstOrNull()

    /** 从磁盘重新读（外部写入后，例如登录页刚保存过） */
    fun reload() {
        items.clear()
        currentUid = null
        if (!file.isFile) return
        try {
            val json = JSONObject(file.readText())
            val current = json.optString("current", "")
            val array = json.optJSONArray("accounts") ?: JSONArray()
            for (i in 0 until array.length()) {
                val obj = array.optJSONObject(i) ?: continue
                val uid = obj.optString("uid", "")
                if (uid.isEmpty()) continue
                val account = Account(uid, GameChannel.fromId(obj.optInt("channel", 5)))
                account.phone = obj.optString("phone", "")
                account.token = obj.optString("token", "")
                account.tokenSavedAt = obj.optLong("tokenSavedAt", 0L)
                account.recordsUpdatedAt = obj.optLong("recordsUpdatedAt", 0L)
                val records = obj.optJSONObject("records")
                if (records != null) {
                    val keys = records.keys()
                    while (keys.hasNext()) {
                        val key = keys.next()
                        val poolType = key.toIntOrNull() ?: continue
                        val array2 = records.optJSONArray(key) ?: continue
                        val list = ArrayList<GachaRecord>()
                        for (j in 0 until array2.length()) {
                            val r = array2.optJSONObject(j) ?: continue
                            list.add(
                                GachaRecord(
                                    poolId = r.optInt("pool_id"),
                                    itemId = r.optInt("item"),
                                    time = r.optLong("time"),
                                    itemNum = r.optInt("item_num", 1)
                                )
                            )
                        }
                        account.records[poolType] = list
                    }
                }
                items[account.key] = account
            }
            if (current.isNotEmpty() && items.containsKey(current)) currentUid = current
        } catch (e: Exception) {
            // 文件损坏就先当空，别覆盖（留给下一次保存）
        }
        if (currentUid == null) currentUid = items.keys.firstOrNull()
    }

    fun save() {
        val array = JSONArray()
        for (account in items.values) {
            val records = JSONObject()
            for ((poolType, list) in account.records) {
                val array2 = JSONArray()
                for (r in list) {
                    array2.put(
                        JSONObject().apply {
                            put("pool_id", r.poolId)
                            put("item", r.itemId)
                            put("time", r.time)
                            put("item_num", r.itemNum)
                        }
                    )
                }
                records.put(poolType.toString(), array2)
            }
            array.put(
                JSONObject().apply {
                    put("uid", account.uid)
                    put("channel", account.channel.id)
                    put("phone", account.phone)
                    put("token", account.token)
                    put("tokenSavedAt", account.tokenSavedAt)
                    put("recordsUpdatedAt", account.recordsUpdatedAt)
                    put("records", records)
                }
            )
        }
        val json = JSONObject().apply {
            put("current", currentUid ?: "")
            put("accounts", array)
        }
        try {
            file.writeText(json.toString())
        } catch (e: Exception) {
        }
    }

    fun select(uid: String): Account? {
        val account = items[uid] ?: return null
        currentUid = uid
        save()
        return account
    }

    /** 登录成功后写入/更新账号（不动别账号的数据） */
    fun upsert(uid: String, phone: String, token: String, channel: GameChannel = GameChannel.OFFICIAL): Account {
        val key = channel.accountKey(uid)
        val account = items.getOrPut(key) { Account(uid, channel) }
        if (phone.isNotEmpty()) account.phone = phone
        if (token.isNotEmpty()) {
            account.token = token
            account.tokenSavedAt = System.currentTimeMillis() / 1000
        }
        currentUid = key
        save()
        return account
    }

    /** 删除一个账号（凭证 + 记录一起删）。删的是当前账号时，自动切到剩下的第一个 */
    fun remove(uid: String): Boolean {
        if (!items.containsKey(uid)) return false
        items.remove(uid)
        if (currentUid == uid) currentUid = items.keys.firstOrNull()
        save()
        return true
    }

    /** 传入账号 key（官服=uid，B服=bili:uid），不是裸 uid —— 与 [putRecords] 一致。 */
    fun invalidateToken(key: String) {
        val account = items[key] ?: return
        account.token = ""
        account.tokenSavedAt = 0L
        save()
    }

    /**
     * 记录只放在内存里，调用方在所有池子拉完后统一 save()（避免主线程反复写大文件）。
     *
     * 与 PC 版一致：新拉到的记录**与本地已有的按 fakeId 合并**，不做覆盖写。
     * 官方记录接口只保留一段时间的记录，窗口一往前滑，覆盖写就会把本地更早的历史弄丢。
     */
    fun putRecords(uid: String, poolType: Int, records: List<GachaRecord>) {
        val account = items[uid] ?: return
        val old = account.records[poolType].orEmpty()
        account.records[poolType] = RecordMerge.merge(records, old)
        account.recordsUpdatedAt = System.currentTimeMillis() / 1000
    }
}
