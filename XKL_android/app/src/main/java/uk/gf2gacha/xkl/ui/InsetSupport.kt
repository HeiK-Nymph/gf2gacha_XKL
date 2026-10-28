package uk.gf2gacha.xkl.ui

import android.view.View
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

/**
 * 给页面底部留出「系统栏 + 手势」安全区。
 *
 * 背景：应用 targetSdk 34、没有开 edge-to-edge，窗口通常会被系统内缩，inset 是 0；
 * 但部分机器（如隐藏导航栏 / 手势导航）底部没有 NAVIGATION_BAR 源，内容会一直贴到
 * 屏幕最下沿，底部按钮正好落在上滑手势区域里。所以这里取
 * `max(系统栏高度, 16dp)` 作为底部留白：
 *   - 三键导航：48dp 左右，按钮浮在导航栏上方；
 *   - 隐藏导航 / 手势：至少 16dp，不贴边。
 *
 * 只加底部，不动顶部（顶部由窗口内缩负责），也不会重复叠加（监听里用的是原始 padding）。
 */
fun View.applyBottomSafeInset(minDp: Int = 16) {
    val base = intArrayOf(paddingLeft, paddingTop, paddingRight, paddingBottom)
    val minPx = (minDp * resources.displayMetrics.density).toInt()
    ViewCompat.setOnApplyWindowInsetsListener(this) { view, insets ->
        val systemBottom = insets.getInsets(WindowInsetsCompat.Type.systemBars()).bottom
        view.setPadding(base[0], base[1], base[2], base[3] + maxOf(systemBottom, minPx))
        insets
    }
    requestApplyInsets()
}
