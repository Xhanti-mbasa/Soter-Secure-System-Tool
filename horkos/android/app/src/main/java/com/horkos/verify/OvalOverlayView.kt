package com.horkos.verify

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View

/** Dims the screen except for a face-shaped oval; the oval outline colour gives feedback. */
class OvalOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    var ovalColor: Int = Color.WHITE
        set(value) {
            field = value
            invalidate()
        }

    private val dim = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xCC000000.toInt() }
    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 12f
    }
    private val path = Path()
    private val oval = RectF()

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat()
        val h = height.toFloat()
        val ow = w * 0.72f
        val oh = ow * 1.3f
        val cx = w / 2f
        val cy = h * 0.45f
        oval.set(cx - ow / 2f, cy - oh / 2f, cx + ow / 2f, cy + oh / 2f)
        path.reset()
        path.fillType = Path.FillType.EVEN_ODD
        path.addRect(0f, 0f, w, h, Path.Direction.CW)
        path.addOval(oval, Path.Direction.CW)
        canvas.drawPath(path, dim)
        stroke.color = ovalColor
        canvas.drawOval(oval, stroke)
    }
}
