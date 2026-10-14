package uk.gf2gacha.xkl.ui

import android.animation.ValueAnimator
import android.graphics.Canvas
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PixelFormat
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.drawable.Drawable
import android.view.animation.LinearInterpolator

/**
 * 斜条纹彩条：**深底色 + 同色系浅色平行四边形斜条**，条纹持续向右移动。
 *
 * 参数按例图实测标定：
 *   - 方向 "\"（左上 → 右下），dx/dy ≈ 0.8（例图实测 +0.89 红 / +0.74 绿）
 *   - 斜条宽 ≈ 条间距（例图 17px : 14px）
 *   - 浅条是**同色系的浅色**（红 #C00000→#C24146、绿 #00B050→#92D050），
 *     不是拿白色往上叠（那样会把颜色冲淡，看着发浅）
 */
class StripeDrawable(
    private val baseColor: Int,
    private val stripeColor: Int,
    private val stripeWidth: Float,
    private val gapWidth: Float,
    private val slope: Float,
    private val cornerRadius: Float,
    durationMs: Long = 900L
) : Drawable() {

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val clipPath = Path()
    private val stripePath = Path()
    private val rect = RectF()
    private var offset = 0f

    private val period: Float get() = stripeWidth + gapWidth

    private val animator = ValueAnimator.ofFloat(0f, 1f).apply {
        duration = durationMs
        repeatCount = ValueAnimator.INFINITE
        interpolator = LinearInterpolator()
        addUpdateListener { animation ->
            offset = (animation.animatedValue as Float) * period
            invalidateSelf()
        }
    }

    override fun draw(canvas: Canvas) {
        val b = bounds
        if (b.isEmpty) return
        if (!animator.isStarted) animator.start()

        rect.set(b.left.toFloat(), b.top.toFloat(), b.right.toFloat(), b.bottom.toFloat())
        clipPath.reset()
        clipPath.addRoundRect(rect, cornerRadius, cornerRadius, Path.Direction.CW)

        val save = canvas.save()
        canvas.clipPath(clipPath)

        paint.color = baseColor
        canvas.drawRect(rect, paint)

        paint.color = stripeColor
        val height = b.height().toFloat()
        val skew = height * slope
        val step = period
        // 从左侧多出一个周期起画，保证左边缘不留空
        var x = b.left - skew - step + (offset % step)
        while (x < b.right + skew) {
            stripePath.reset()
            // "\" 方向：上边靠左，下边靠右
            stripePath.moveTo(x, b.top.toFloat())
            stripePath.lineTo(x + skew, b.bottom.toFloat())
            stripePath.lineTo(x + skew + stripeWidth, b.bottom.toFloat())
            stripePath.lineTo(x + stripeWidth, b.top.toFloat())
            stripePath.close()
            canvas.drawPath(stripePath, paint)
            x += step
        }

        canvas.restoreToCount(save)
    }

    override fun setAlpha(alpha: Int) {
        paint.alpha = alpha
        invalidateSelf()
    }

    override fun setColorFilter(colorFilter: ColorFilter?) {
        paint.colorFilter = colorFilter
        invalidateSelf()
    }

    @Deprecated("Deprecated in Java")
    override fun getOpacity(): Int = PixelFormat.TRANSLUCENT

    override fun onBoundsChange(bounds: Rect) {
        super.onBoundsChange(bounds)
        invalidateSelf()
    }

    override fun setVisible(visible: Boolean, restart: Boolean): Boolean {
        if (visible) {
            if (!animator.isStarted) animator.start()
        } else {
            animator.cancel()
        }
        return super.setVisible(visible, restart)
    }
}