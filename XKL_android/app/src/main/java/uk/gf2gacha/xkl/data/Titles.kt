package uk.gf2gacha.xkl.data

/**
 * 把统计数字翻译成称号 / 标签（纯展示，规则集中在这里方便调）。
 *
 * 保底 80 抽的依据：PC 版进度条每次 +1.25% -> 满进度 80 抽。
 */
object Titles {

    const val HARD_PITY = 80

    fun title(totalPulls: Int, ssrCount: Int): String {
        if (ssrCount == 0) return "尚未开张"
        val average = totalPulls.toFloat() / ssrCount
        return when {
            average <= 25f -> "万里挑一的欧皇"
            average <= 35f -> "欧气侧漏"
            average <= 45f -> "稳定发挥"
            average <= 55f -> "非酋预备军"
            average <= 65f -> "非洲常驻代表"
            else -> "保底战神"
        }
    }

    fun tags(totalPulls: Int, ssrCount: Int, pity: Int, maxCost: Int): List<String> {
        val list = ArrayList<String>()
        if (ssrCount == 0) return list
        val average = totalPulls.toFloat() / ssrCount
        if (average <= 30f) list.add("一鸣惊人")
        if (ssrCount >= 10) list.add("五星收集者")
        if (maxCost >= HARD_PITY - 2) list.add("保底边缘")
        if (pity >= HARD_PITY * 3 / 4) list.add("即将见金")
        if (average >= 55f) list.add("非到极致")
        return list.take(3)
    }
}