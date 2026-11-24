package uk.gf2gacha.xkl.data

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * 抽数统计回归用例。
 *
 * 官方 /list 接口把同一秒（= 一次十连的 10 条）按「新→旧」返回，列表最上面那条是这十连的最后一抽；
 * RecordMerge 落盘时保持这个顺序，所以统计必须先把同秒组翻成「旧→新」再累加垫抽，
 * 否则每个十连都被倒着数，五星抽数和当前垫抽全会错。
 *
 * 用例取自一次真实十连的官方响应结构（已脱敏：只保留道具 id，时间戳换成占位值）。
 */
class GachaChronologyTest {

    private val ssr = mapOf(1029 to "塞布丽娜", 1088 to "破坏者")

    private fun record(itemId: Int, time: Long) = GachaRecord(0, itemId, time, 1)

    private val window = listOf(
        // 后一个十连：寇尔芙那一抽在最上面（最后出），塞布丽娜是倒数第 2 抽
        record(1009, 2000), record(1029, 2000), record(11036, 2000),
        record(11009, 2000), record(1026, 2000), record(10891, 2000),
        record(11024, 2000), record(10492, 2000), record(10331, 2000),
        record(10891, 2000),
        // 前一个十连：破坏者排在同秒组第一 → 它是这十连的最后一抽，出金后垫抽归零
        record(1088, 1000), record(11039, 1000), record(10431, 1000),
        record(11022, 1000), record(11048, 1000), record(11024, 1000),
        record(11045, 1000), record(1001, 1000), record(11039, 1000),
        record(10432, 1000)
    )

    @Test
    fun `破坏者之后那一十连，塞布丽娜是第 9 抽而不是 11 抽`() {
        val (hits, pity) = analyzeHits(
            window,
            name = { ssr[it.itemId] },
            isWai = { false }
        )
        assertEquals(listOf("破坏者", "塞布丽娜"), hits.map { it.name })
        assertEquals(9, hits[1].costDraws)
        assertEquals(1, pity)
        // 窗口从破坏者那一十连开始，所以它在窗口内是第 10 抽
        assertEquals(10, hits[0].costDraws)
        assertEquals(20, hits.sumOf { it.costDraws } + pity)
    }

    @Test
    fun `chronological 同秒内翻成旧到新且整体时间升序`() {
        val ordered = chronological(window)
        assertEquals(1000L, ordered.first().time)
        assertEquals(2000L, ordered.last().time)
        val latestSecond = ordered.filter { it.time == 2000L }
        assertEquals(10, latestSecond.size)
        // 接口里第一条（1009，寇尔芙）是最后一抽 → 翻过来后排在末尾；接口最后一条是这一秒的第一抽
        assertEquals(1009, latestSecond.last().itemId)
        assertEquals(10891, latestSecond.first().itemId)
    }

    @Test
    fun `跨秒顺序不受影响且五星按时间升序返回`() {
        val (hits, _) = analyzeHits(window, name = { ssr[it.itemId] }, isWai = { false })
        assertEquals(true, hits[0].time < hits[1].time)
    }
}
