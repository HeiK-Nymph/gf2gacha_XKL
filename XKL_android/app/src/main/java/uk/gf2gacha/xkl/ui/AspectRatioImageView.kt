package uk.gf2gacha.xkl.ui

import android.content.Context
import android.util.AttributeSet
import androidx.appcompat.widget.AppCompatImageView

/** 公告图片按原始宽高比测量；竖长图最多占 520dp，避免弹窗被单张图撑爆。 */
class AspectRatioImageView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : AppCompatImageView(context, attrs, defStyleAttr) {

    private val maxHeightPx = (520f * resources.displayMetrics.density).toInt()

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val drawable = drawable
        val width = MeasureSpec.getSize(widthMeasureSpec)
        if (drawable == null || drawable.intrinsicWidth <= 0 || drawable.intrinsicHeight <= 0 || width <= 0) {
            super.onMeasure(widthMeasureSpec, heightMeasureSpec)
            return
        }
        val desired = (width.toLong() * drawable.intrinsicHeight / drawable.intrinsicWidth)
            .toInt()
            .coerceAtMost(maxHeightPx)
            .coerceAtLeast(1)
        setMeasuredDimension(width, desired)
    }
}
