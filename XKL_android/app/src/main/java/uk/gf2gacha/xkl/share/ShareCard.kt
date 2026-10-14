package uk.gf2gacha.xkl.share

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Typeface
import okhttp3.OkHttpClient
import okhttp3.Request
import uk.gf2gacha.xkl.R
import uk.gf2gacha.xkl.data.Gf2Api
import uk.gf2gacha.xkl.data.PoolResult
import uk.gf2gacha.xkl.data.SsrHit
import uk.gf2gacha.xkl.data.SsrTable
import uk.gf2gacha.xkl.data.Titles
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * 分享图（竖版长图，暗金风格 = App 自己的样式）。
 *
 * 企业级分享图的通行做法：**固定宽度 + 高度自适应 + 不做一屏压缩**。
 * 这里宽固定 360dp（×3 = 1080px，与手机屏同宽），所以图里的字号/头像/彩条
 * 在 100% 放大时和 App 里**一样大**，长图交给用户自己缩放。
 *
 * 一图只出**当前卡池**（要发别的池就切过去再分享一次）。
 */
object ShareCard {

    private const val SCALE = 3f
    private const val W = 360f
    private const val PAD = 16f
    private const val ROW_H = 46f
    private const val AVATAR = 36f
    private const val BAR_H = 22f
    private const val COST_W = 44f
    // 右侧「歪 + 名字」的固定槽位（必须与 App 的 item_ssr_bar.xml 一致）：
    // 歪 6dp margin + 26dp，名字 8dp margin + 68dp。
    private const val WAI_GAP = 6f
    private const val WAI_SLOT = 26f
    private const val NAME_GAP = 8f
    private const val NAME_SLOT = 68f
    /** 一行五星右侧被固定占掉的宽度；彩条的最大长度 = 总宽 - 左边三块 - 它 */
    private const val RIGHT_BLOCK = WAI_GAP + WAI_SLOT + NAME_GAP + NAME_SLOT

    private val BG = Color.parseColor("#0E0E11")
    private val CARD = Color.parseColor("#17171C")
    private val STROKE = Color.parseColor("#2A2A32")
    private val PILL = Color.parseColor("#23232B")
    private val GOLD = Color.parseColor("#E8C170")
    private val GOLD_BRIGHT = Color.parseColor("#FFD98A")
    private val TEXT = Color.parseColor("#F2F2F5")
    private val DIM = Color.parseColor("#8E8E99")
    private val GREEN = Color.parseColor("#00B050")
    private val YELLOW = Color.parseColor("#FFC000")
    private val RED = Color.parseColor("#C00000")
    private val WAI = Color.parseColor("#D05A4A")

    private val client = OkHttpClient.Builder()
        .connectTimeout(6, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    fun render(
        context: Context,
        allResults: Collection<PoolResult>,
        pool: Gf2Api.Pool,
        result: PoolResult
    ): Bitmap {
        val table = SsrTable.get(context)
        val appName = context.getString(R.string.app_name)
        val avatars = loadAvatars(result, table)

        // ---- 顶部汇总（五池合计，和主界面一致）----
        val total = allResults.sumOf { it.total }
        val ssr = allResults.sumOf { it.ssrCount }
        val limited = listOf(
            Gf2Api.POOL_CHARACTER, Gf2Api.POOL_WEAPON,
            Gf2Api.POOL_CUSTOM_CHARACTER, Gf2Api.POOL_CUSTOM_WEAPON
        )
        val limitedSsr = limited.sumOf { type -> allResults.firstOrNull { it.poolType == type }?.ssrCount ?: 0 }
        val limitedWai = limited.sumOf { type -> allResults.firstOrNull { it.poolType == type }?.waiCount ?: 0 }
        val notWai = if (limitedSsr == 0) "—"
        else String.format(java.util.Locale.US, "%.1f%%", (limitedSsr - limitedWai) * 100.0 / limitedSsr)
        val average = if (ssr == 0) "—" else Math.round(total.toFloat() / ssr).toString() + " 抽"
        val title = Titles.title(total, ssr)
        val maxPity = allResults.maxOfOrNull { it.pity } ?: 0
        val maxCost = allResults.maxOfOrNull { it.maxCost } ?: 0
        val tags = Titles.tags(total, ssr, maxPity, maxCost)

        // ---- 池名+统计那行（跟 App 一样会换行，先量好行数再算高度）----
        val waiText = if (pool.typeId == Gf2Api.POOL_PERMANENT) "" else " · 歪 " + result.waiCount + " 个"
        val poolText = pool.name + " · 共 " + result.total + " 抽 · 五星 " + result.ssrCount + " 个" +
            waiText + " · 当前垫 " + result.pity + " 抽"
        val poolPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            typeface = Typeface.DEFAULT_BOLD
            textSize = 15f
        }
        val poolLines = wrap(poolPaint, poolText, W - PAD * 2)

        // ---- 高度预算 ----
        val rows = result.ssrCount.coerceAtLeast(1)
        var height = PAD
        height += 24f                                    // 品牌行
        height += 36f                                    // 称号
        height += 52f                                    // 三个大数字
        if (tags.isNotEmpty()) height += 34f             // 标签胶囊
        height += 74f                                    // 四格统计卡
        height += 20f + poolLines.size * 22f              // 池名 + 统计（可能两行）
        height += ROW_H                                  // 垫抽行
        height += rows * ROW_H                           // 五星列表
        height += 40f                                    // 页脚
        height += PAD

        val bitmap = Bitmap.createBitmap((W * SCALE).toInt(), (height * SCALE).toInt(), Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        canvas.scale(SCALE, SCALE)
        canvas.drawColor(BG)

        val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        var y = PAD

        // ---- 品牌行：只留 App 名（不放 UID / 更新时间，避免分享时泄露账号信息）----
        paint.typeface = Typeface.DEFAULT_BOLD
        paint.textSize = 15f
        paint.color = GOLD
        paint.textAlign = Paint.Align.LEFT
        canvas.drawText(appName, PAD, y + 16f, paint)
        y += 24f

        // ---- 称号（主视觉）----
        paint.typeface = Typeface.DEFAULT_BOLD
        paint.textSize = 26f
        paint.color = GOLD
        canvas.drawText(title, PAD, y + 26f, paint)
        y += 36f

        // ---- 三个大数字：总抽卡数 / 平均出金 / 小保不歪 ----
        val colW = (W - PAD * 2) / 3f
        drawHero(canvas, paint, PAD + colW * 0f, y, colW, "$total 抽", "总抽卡数")
        drawHero(canvas, paint, PAD + colW * 1f, y, colW, average, "平均出金")
        drawHero(canvas, paint, PAD + colW * 2f, y, colW, notWai, "小保不歪")
        y += 52f

        // ---- 标签胶囊 ----
        if (tags.isNotEmpty()) {
            var x = PAD
            for (tag in tags) {
                paint.typeface = Typeface.DEFAULT
                paint.textSize = 12f
                val textW = paint.measureText(tag)
                val pillW = textW + 24f
                paint.color = PILL
                canvas.drawRoundRect(RectF(x, y, x + pillW, y + 26f), 13f, 13f, paint)
                paint.style = Paint.Style.STROKE
                paint.strokeWidth = 1f
                paint.color = STROKE
                canvas.drawRoundRect(RectF(x, y, x + pillW, y + 26f), 13f, 13f, paint)
                paint.style = Paint.Style.FILL
                paint.color = GOLD
                canvas.drawText(tag, x + 12f, y + 17f, paint)
                x += pillW + 8f
            }
            y += 34f
        }

        // ---- 四格统计卡（五星数 / 角色平均 / 武器平均 / 常驻平均）----
        val cardH = 62f
        paint.color = CARD
        canvas.drawRoundRect(RectF(PAD, y, W - PAD, y + cardH), 12f, 12f, paint)
        paint.style = Paint.Style.STROKE
        paint.strokeWidth = 1f
        paint.color = STROKE
        canvas.drawRoundRect(RectF(PAD, y, W - PAD, y + cardH), 12f, 12f, paint)
        paint.style = Paint.Style.FILL
        val statW = (W - PAD * 2) / 4f
        val charAvg = averageOf(allResults, intArrayOf(3, 6))
        val weaponAvg = averageOf(allResults, intArrayOf(4, 7))
        val permAvg = averageOf(allResults, intArrayOf(1))
        drawHero(canvas, paint, PAD + statW * 0f, y + 10f, statW, ssr.toString(), "五星数", 20f)
        drawHero(canvas, paint, PAD + statW * 1f, y + 10f, statW, charAvg, "角色平均", 20f)
        drawHero(canvas, paint, PAD + statW * 2f, y + 10f, statW, weaponAvg, "武器平均", 20f)
        drawHero(canvas, paint, PAD + statW * 3f, y + 10f, statW, permAvg, "常驻平均", 20f)
        y += cardH + 14f

        // ---- 池名 + 统计 ----
        paint.typeface = Typeface.DEFAULT_BOLD
        paint.textSize = 15f
        paint.color = GOLD
        for (line in poolLines) {
            canvas.drawText(line, PAD, y + 18f, paint)
            y += 22f
        }
        y += 6f

        // ---- 垫抽行（问号 + 垫抽数 + 金条 + 已垫 N 抽）----
        drawPityRow(canvas, paint, result, y)
        y += ROW_H

        // ---- 五星列表 ----
        val hits = result.ssrHits.sortedByDescending { it.time }
        if (hits.isEmpty()) {
            paint.typeface = Typeface.DEFAULT
            paint.textSize = 13f
            paint.color = DIM
            canvas.drawText("这个池子还没出过五星", PAD, y + 24f, paint)
        } else {
            for (hit in hits) {
                drawHitRow(canvas, paint, table, avatars, hit, y)
                y += ROW_H
            }
        }

        // ---- 页脚 ----
        y += 14f
        paint.typeface = Typeface.DEFAULT
        paint.textSize = 11f
        paint.color = DIM
        paint.textAlign = Paint.Align.CENTER
        canvas.drawText("由「" + appName + "」生成 · 数据来自官方接口", W / 2f, y + 12f, paint)
        paint.textAlign = Paint.Align.LEFT

        return bitmap
    }

    /** 按空格断行（和 TextView 的换行行为一致） */
    private fun wrap(paint: Paint, text: String, maxWidth: Float): List<String> {
        val lines = ArrayList<String>()
        var line = StringBuilder()
        for (word in text.split(" ")) {
            val candidate = if (line.isEmpty()) word else line.toString() + " " + word
            if (line.isNotEmpty() && paint.measureText(candidate) > maxWidth) {
                lines.add(line.toString())
                line = StringBuilder(word)
            } else {
                line = StringBuilder(candidate)
            }
        }
        if (line.isNotEmpty()) lines.add(line.toString())
        return lines
    }

    /** 一列：上面大字（金色加粗），下面小标签（灰） */
    private fun drawHero(
        canvas: Canvas,
        paint: Paint,
        x: Float,
        y: Float,
        width: Float,
        value: String,
        label: String,
        valueSize: Float = 26f
    ) {
        paint.textAlign = Paint.Align.CENTER
        paint.typeface = Typeface.DEFAULT_BOLD
        paint.textSize = valueSize
        paint.color = GOLD_BRIGHT
        canvas.drawText(value, x + width / 2f, y + valueSize * 0.9f, paint)

        paint.typeface = Typeface.DEFAULT
        paint.textSize = 11f
        paint.color = DIM
        canvas.drawText(label, x + width / 2f, y + valueSize * 0.9f + 16f, paint)
        paint.textAlign = Paint.Align.LEFT
    }

    private fun drawPityRow(canvas: Canvas, paint: Paint, result: PoolResult, y: Float) {
        val cy = y + ROW_H / 2f
        // 问号徽标
        paint.color = PILL
        canvas.drawCircle(PAD + AVATAR / 2f, cy, AVATAR / 2f, paint)
        paint.textAlign = Paint.Align.CENTER
        paint.typeface = Typeface.DEFAULT
        paint.textSize = 15f
        paint.color = GOLD
        canvas.drawText("?", PAD + AVATAR / 2f, cy + 5f, paint)

        // 垫抽数（与五星行的抽数同列）
        paint.typeface = Typeface.DEFAULT_BOLD
        paint.textSize = 15f
        paint.color = GOLD
        canvas.drawText(result.pity.toString(), PAD + AVATAR + COST_W / 2f, cy + 5f, paint)
        paint.textAlign = Paint.Align.LEFT

        // 金条：右端扣掉和五星行一样的固定槽位，两处条长才能完全一致
        val barX = PAD + AVATAR + COST_W
        val label = "已垫 " + result.pity + " 抽"
        val barMax = (W - PAD - barX - RIGHT_BLOCK).coerceAtLeast(24f)
        val fraction = (result.pity / Titles.HARD_PITY.toFloat()).coerceIn(0f, 1f)
        // 和 App 一样只画彩条，不画底下的空槽
        if (fraction > 0f) {
            paint.color = GOLD
            canvas.drawRoundRect(
                RectF(barX, cy - BAR_H / 2f, barX + barMax * fraction, cy + BAR_H / 2f), 6f, 6f, paint
            )
        }
        paint.typeface = Typeface.DEFAULT
        paint.textSize = 12f
        paint.color = GOLD
        canvas.drawText(label, W - PAD - NAME_SLOT, cy + 4f, paint)
    }

    /** 一行五星：头像 + 抽数 + 彩条 + 歪标签 + 名字（尺寸/配色与 App 完全一致） */
    private fun drawHitRow(
        canvas: Canvas,
        paint: Paint,
        table: SsrTable,
        avatars: Map<Int, Bitmap>,
        hit: SsrHit,
        y: Float
    ) {
        val isWeapon = table.isWeaponItem(hit.itemId)
        val cy = y + ROW_H / 2f
        val avatarBmp = avatars[hit.itemId]

        // 头像 / 武
        if (!isWeapon && avatarBmp != null) {
            val save = canvas.save()
            val path = Path().apply {
                addCircle(PAD + AVATAR / 2f, cy, AVATAR / 2f, Path.Direction.CW)
            }
            canvas.clipPath(path)
            canvas.drawBitmap(
                avatarBmp, null,
                RectF(PAD, cy - AVATAR / 2f, PAD + AVATAR, cy + AVATAR / 2f), paint
            )
            canvas.restoreToCount(save)
        } else {
            paint.color = PILL
            canvas.drawCircle(PAD + AVATAR / 2f, cy, AVATAR / 2f, paint)
            paint.textAlign = Paint.Align.CENTER
            paint.typeface = Typeface.DEFAULT
            paint.textSize = 11f
            paint.color = DIM
            canvas.drawText(if (isWeapon) "武" else "？", PAD + AVATAR / 2f, cy + 4f, paint)
            paint.textAlign = Paint.Align.LEFT
        }

        // 抽数（颜色与 PC/App 同阈值）
        val barColor = when {
            hit.costDraws < 30 -> GREEN
            hit.costDraws < 60 -> YELLOW
            else -> RED
        }
        paint.textAlign = Paint.Align.CENTER
        paint.typeface = Typeface.DEFAULT_BOLD
        paint.textSize = 15f
        paint.color = barColor
        canvas.drawText(hit.costDraws.toString(), PAD + AVATAR + COST_W / 2f, cy + 5f, paint)
        paint.textAlign = Paint.Align.LEFT

        // 名字 + 歪标签：两块都占**固定槽位**（和 App 的 item_ssr_bar.xml 一致）。
        // 彩条长度只由抽数决定 —— 名字长短、有没有「歪」都不会再挤压它。
        paint.typeface = Typeface.DEFAULT
        paint.textSize = 12f
        val nameLeft = W - PAD - NAME_SLOT
        val waiLeft = nameLeft - NAME_GAP - WAI_SLOT
        val barX = PAD + AVATAR + COST_W
        val barMax = (waiLeft - WAI_GAP - barX).coerceAtLeast(24f)
        val barW = (hit.costDraws / Titles.HARD_PITY.toFloat()).coerceIn(0.05f, 1f) * barMax

        // 和 App 一样只画彩条，不画底下的空槽
        paint.color = barColor
        canvas.drawRoundRect(RectF(barX, cy - BAR_H / 2f, barX + barW, cy + BAR_H / 2f), 6f, 6f, paint)

        // 顺序与 App 一致：[彩条][歪][名字]
        if (hit.isWai) {
            paint.color = WAI
            canvas.drawRoundRect(RectF(waiLeft, cy - 9f, waiLeft + WAI_SLOT, cy + 9f), 4f, 4f, paint)
            paint.textAlign = Paint.Align.CENTER
            paint.typeface = Typeface.DEFAULT
            paint.textSize = 11f
            paint.color = TEXT
            canvas.drawText("歪", waiLeft + WAI_SLOT / 2f, cy + 4f, paint)
            paint.textAlign = Paint.Align.LEFT
        }

        paint.typeface = Typeface.DEFAULT
        paint.textSize = 12f
        paint.color = GOLD
        canvas.drawText(fitName(paint, hit.name, NAME_SLOT), nameLeft, cy + 4f, paint)
    }

    /** 名字超过槽位宽度时按字符裁剪加省略号（不会再撑宽/挤窄彩条） */
    private fun fitName(paint: Paint, name: String, maxWidth: Float): String {
        if (paint.measureText(name) <= maxWidth) return name
        var text = name
        while (text.isNotEmpty() && paint.measureText(text + "…") > maxWidth) {
            text = text.substring(0, text.length - 1)
        }
        return text + "…"
    }

    private fun averageOf(all: Collection<PoolResult>, types: IntArray): String {
        var total = 0
        var ssr = 0
        for (type in types) {
            val result = all.firstOrNull { it.poolType == type } ?: continue
            total += result.total
            ssr += result.ssrCount
        }
        return if (ssr == 0) "—" else Math.round(total.toFloat() / ssr).toString() + "抽"
    }

    /** 并行拉本池五星人形的头像（失败就画占位圈） */
    private fun loadAvatars(result: PoolResult, table: SsrTable): Map<Int, Bitmap> {
        val ids = LinkedHashSet<Int>()
        for (hit in result.ssrHits) {
            if (!table.isWeaponItem(hit.itemId)) ids.add(hit.itemId)
        }
        if (ids.isEmpty()) return emptyMap()
        val executor = Executors.newFixedThreadPool(6)
        val out = HashMap<Int, Bitmap>()
        val futures = ids.map { id ->
            executor.submit {
                try {
                    val request = Request.Builder().url(Gf2Api.IMAGE_BASE + id + ".png").build()
                    client.newCall(request).execute().use { response ->
                        if (response.isSuccessful) {
                            val bitmap = BitmapFactory.decodeStream(response.body?.byteStream())
                            if (bitmap != null) synchronized(out) { out[id] = bitmap }
                        }
                    }
                } catch (e: Exception) {
                }
            }
        }
        for (future in futures) {
            try {
                future.get(15, TimeUnit.SECONDS)
            } catch (e: Exception) {
            }
        }
        executor.shutdown()
        return out
    }
}