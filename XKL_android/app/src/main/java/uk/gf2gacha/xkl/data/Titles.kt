package uk.gf2gacha.xkl.data

/**
 * 把统计数字翻译成称号 / 标签（纯展示，规则集中在这里方便调）。
 *
 * 2026-10-29 起称号改用「UP 口径」：
 *   - 玩家要的是 UP，歪掉的金不算成绩，所以算「平均每个 UP 花了多少抽」，不再算「平均每个金」。
 *   - 角色池（3/6）期望 80.4 抽 / UP：0.6% 基础 + 59 抽起每抽 +4.7pp、80 硬保底、
 *     出金 50% UP、歪后必 UP（大保底）。
 *   - 武器池（4/7）期望 58.2 抽 / UP：0.7% 基础 + 51 抽起每抽 +5.3pp、70 硬保底、
 *     出金 75% UP、歪后必 UP。
 *   - 两池用「实际 ÷ 该池期望」的倍率共用一套阈值，避免一套绝对抽数把武器池判得偏欧。
 *
 * 保底值按池：角色 / 常驻 80，武器 70。
 * 小程序端 `miniprogram/utils/title-rules.js` 与云函数 `cloudfunctions/ranking/score.js`
 * 是同一套规则的副本，改这里必须同步改那两处（tools/title-rules.test.js 会对拍）。
 */
object Titles {

    const val HARD_PITY = 80
    const val HARD_PITY_WEAPON = 70

    /** 期望抽数 / UP，由概率曲线积分算出（见 .runtime/gacha_ev2.py） */
    private const val EXPECT_UP_CHARACTER = 80.35
    private const val EXPECT_UP_WEAPON = 58.15

    /** 偏「非」的倍率边界，同时用于称号和「非到极致」 */
    private const val UNLUCKY_RATIO = 1.40

    private val LIMITED = intArrayOf(
        Gf2Api.POOL_CHARACTER, Gf2Api.POOL_WEAPON,
        Gf2Api.POOL_CUSTOM_CHARACTER, Gf2Api.POOL_CUSTOM_WEAPON
    )

    /** 该池硬保底：角色 / 常驻 80，武器 70 */
    fun hardPity(poolType: Int): Int =
        if (poolType == Gf2Api.POOL_WEAPON || poolType == Gf2Api.POOL_CUSTOM_WEAPON) {
            HARD_PITY_WEAPON
        } else {
            HARD_PITY
        }

    private fun expectUp(poolType: Int): Double =
        if (hardPity(poolType) == HARD_PITY_WEAPON) EXPECT_UP_WEAPON else EXPECT_UP_CHARACTER

    private fun limited(pools: Collection<PoolResult>): List<PoolResult> =
        pools.filter { it.poolType in LIMITED }

    /** UP 数：限定池里非歪的五星 */
    private fun upCount(pools: Collection<PoolResult>): Int =
        pools.sumOf { pool -> pool.ssrHits.count { hit -> !hit.isWai } }

    /** 这些抽数「按期望本来该出几个 UP」——用来和实际 UP 数做比值 */
    private fun expectedUpDraws(pools: Collection<PoolResult>): Double =
        pools.sumOf { it.total / expectUp(it.poolType) }

    fun title(pools: Collection<PoolResult>): String {
        if (pools.sumOf { it.ssrCount } == 0) return "尚未开张"
        val limitedPools = limited(pools)
        val limitedDraws = limitedPools.sumOf { it.total }
        val up = upCount(limitedPools)
        if (up == 0) {
            // 完全没碰限定池（只抽过常驻）时退回旧的「出金」口径，
            // 避免把常驻玩家判成「只歪不中」——常驻池本来就没有歪的概念。
            return if (limitedDraws == 0) goldTitle(pools) else "只歪不中"
        }
        val ratio = expectedUpDraws(limitedPools) / up
        return when {
            ratio <= 0.65 -> "万里挑一的欧皇"
            ratio <= 0.85 -> "欧气侧漏"
            ratio <= 1.10 -> "稳定发挥"
            ratio <= UNLUCKY_RATIO -> "非酋预备军"
            ratio <= 1.75 -> "非洲常驻代表"
            else -> "保底战神"
        }
    }

    /** 旧版「平均出金」口径，只在完全没有限定池数据时兜底 */
    private fun goldTitle(pools: Collection<PoolResult>): String {
        val average = pools.sumOf { it.total }.toDouble() / pools.sumOf { it.ssrCount }
        return when {
            average <= 25 -> "万里挑一的欧皇"
            average <= 35 -> "欧气侧漏"
            average <= 45 -> "稳定发挥"
            average <= 55 -> "非酋预备军"
            average <= 65 -> "非洲常驻代表"
            else -> "保底战神"
        }
    }

    fun tags(pools: Collection<PoolResult>): List<String> {
        val list = ArrayList<String>()
        val ssr = pools.sumOf { it.ssrCount }
        if (ssr == 0) return list
        val average = pools.sumOf { it.total }.toDouble() / ssr
        if (average <= 30.0) list.add("一鸣惊人")
        if (ssr >= 10) list.add("五星收集者")
        // 保底边缘：单次出金距离该池硬保底 10 抽以内（角色 ≥70，武器 ≥60）
        if (pools.any { pool ->
                (pool.ssrHits.maxOfOrNull { it.costDraws } ?: 0) >= hardPity(pool.poolType) - 10
            }) {
            list.add("保底边缘")
        }
        // 即将见金：当前垫抽已到该池硬保底的 3/4（角色 60，武器 53）
        if (pools.any { pool -> pool.pity * 4 >= hardPity(pool.poolType) * 3 }) {
            list.add("即将见金")
        }
        val limitedPools = limited(pools)
        val up = upCount(limitedPools)
        val unlucky = if (up == 0) {
            limitedPools.sumOf { it.total } > 0
        } else {
            expectedUpDraws(limitedPools) / up >= UNLUCKY_RATIO
        }
        if (unlucky) list.add("非到极致")
        return list.take(3)
    }
}
