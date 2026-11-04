package com.horkos.verify

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Matrix
import android.graphics.Rect
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.facemesh.FaceMeshDetection
import com.google.mlkit.vision.facemesh.FaceMeshDetectorOptions
import kotlin.math.atan2
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min

/** 468-point face mesh, 2D parallax depth cue, colour sampling and debug drawing. */
object FaceAnalysis {
    const val NOSE_TIP = 1
    const val LEFT_CHEEK = 234
    const val RIGHT_CHEEK = 454

    private val meshDetector by lazy {
        FaceMeshDetection.getClient(
            FaceMeshDetectorOptions.Builder().setUseCase(FaceMeshDetectorOptions.FACE_MESH).build()
        )
    }

    /** Mesh points (x, y, z) for the largest face, ordered by MediaPipe index. Call off the main thread. */
    fun mesh(bitmap: Bitmap): List<FloatArray>? {
        val meshes = Tasks.await(meshDetector.process(InputImage.fromBitmap(bitmap, 0)))
        val m = meshes.maxByOrNull { it.boundingBox.width() * it.boundingBox.height() } ?: return null
        return m.allPoints.sortedBy { it.index }.map { floatArrayOf(it.position.x, it.position.y, it.position.z) }
    }

    /** Mesh on the full frame; if that fails, retry on an enlarged (upscaled) face crop and map back. */
    fun meshWithFallback(frame: Bitmap, box: Rect): List<FloatArray>? {
        mesh(frame)?.let { return it }
        val r = ImageUtils.cropRect(frame, box, 0.4f)
        val crop = Bitmap.createBitmap(frame, r.left, r.top, r.width(), r.height())
        val up = if (crop.width < 320) Bitmap.createScaledBitmap(crop, crop.width * 2, crop.height * 2, true) else crop
        val s = crop.width.toFloat() / up.width
        val m = mesh(up) ?: return null
        return m.map { p -> floatArrayOf(r.left + p[0] * s, r.top + p[1] * s, p[2] * s) }
    }

    /**
     * Horizontal offset of the nose tip from the midpoint of the cheeks, divided by cheek distance.
     * A real 3D face shifts strongly when the head turns; a flat photo keeps the same ratio.
     */
    fun parallax(mesh: List<FloatArray>?): Float? {
        if (mesh == null || mesh.size <= RIGHT_CHEEK) return null
        val n = mesh[NOSE_TIP]
        val l = mesh[LEFT_CHEEK]
        val r = mesh[RIGHT_CHEEK]
        val width = hypot(l[0] - r[0], l[1] - r[1])
        if (width < 1f) return null
        return (n[0] - (l[0] + r[0]) / 2f) / width
    }

    /** Nose depth relative to the cheeks, from the mesh's estimated z values. */
    fun noseDepth(mesh: List<FloatArray>?): Float? {
        if (mesh == null || mesh.size <= RIGHT_CHEEK) return null
        return mesh[NOSE_TIP][2] - (mesh[LEFT_CHEEK][2] + mesh[RIGHT_CHEEK][2]) / 2f
    }

    /** Copy of the frame with mesh dots (green), anchor points (red) and face box (yellow), cropped to the face. */
    fun drawMesh(frame: Bitmap, mesh: List<FloatArray>?, box: Rect?): Bitmap {
        val out = frame.copy(Bitmap.Config.ARGB_8888, true)
        val c = Canvas(out)
        val r = max(1.5f, frame.width / 320f)
        val dot = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.GREEN }
        val key = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.RED }
        mesh?.forEachIndexed { i, p ->
            if (i == NOSE_TIP || i == LEFT_CHEEK || i == RIGHT_CHEEK) c.drawCircle(p[0], p[1], r * 3f, key)
            else c.drawCircle(p[0], p[1], r, dot)
        }
        if (box == null) return out
        val stroke = Paint().apply {
            color = Color.YELLOW
            style = Paint.Style.STROKE
            strokeWidth = r
        }
        c.drawRect(box, stroke)
        return ImageUtils.cropFace(out, box, 0.35f)
    }

    /** Mean RGB of the inner part of the face box. */
    fun meanRgb(frame: Bitmap, box: Rect): FloatArray {
        val l = max(0, box.left + box.width() / 5)
        val t = max(0, box.top + box.height() / 5)
        val rgt = min(frame.width - 1, box.right - box.width() / 5)
        val b = min(frame.height - 1, box.bottom - box.height() / 5)
        var sr = 0.0
        var sg = 0.0
        var sb = 0.0
        var n = 0
        var y = t
        while (y < b) {
            var x = l
            while (x < rgt) {
                val p = frame.getPixel(x, y)
                sr += Color.red(p)
                sg += Color.green(p)
                sb += Color.blue(p)
                n++
                x += 3
            }
            y += 3
        }
        if (n == 0) return floatArrayOf(0f, 0f, 0f)
        return floatArrayOf((sr / n).toFloat(), (sg / n).toFloat(), (sb / n).toFloat())
    }

    /**
     * Rotates and scales the face so the eye centres land where MobileFaceNet/ArcFace expect them
     * in a 112x112 crop (eyes level, 35.2 px apart, centred at (56, 51.6)).
     */
    fun align(frame: Bitmap, mesh: List<FloatArray>?): Bitmap? {
        if (mesh == null || mesh.size <= 362) return null
        val e1x = (mesh[33][0] + mesh[133][0]) / 2f
        val e1y = (mesh[33][1] + mesh[133][1]) / 2f
        val e2x = (mesh[263][0] + mesh[362][0]) / 2f
        val e2y = (mesh[263][1] + mesh[362][1]) / 2f
        val firstIsLeft = e1x <= e2x
        val lx = if (firstIsLeft) e1x else e2x
        val ly = if (firstIsLeft) e1y else e2y
        val rx = if (firstIsLeft) e2x else e1x
        val ry = if (firstIsLeft) e2y else e1y
        val dist = hypot(rx - lx, ry - ly)
        if (dist < 6f) return null
        val angle = Math.toDegrees(atan2((ry - ly).toDouble(), (rx - lx).toDouble())).toFloat()
        val scale = 35.2f / dist
        val m = Matrix()
        m.postTranslate(-(lx + rx) / 2f, -(ly + ry) / 2f)
        m.postRotate(-angle)
        m.postScale(scale, scale)
        m.postTranslate(56f, 51.6f)
        val out = Bitmap.createBitmap(112, 112, Bitmap.Config.ARGB_8888)
        Canvas(out).drawBitmap(frame, m, Paint(Paint.FILTER_BITMAP_FLAG))
        return out
    }

    /** Mean RGB of a whole rectangle (no inset), sampled every 4 px. */
    fun meanRgbRect(frame: Bitmap, rect: Rect): FloatArray {
        val l = max(0, rect.left)
        val t = max(0, rect.top)
        val rgt = min(frame.width - 1, rect.right)
        val b = min(frame.height - 1, rect.bottom)
        var sr = 0.0
        var sg = 0.0
        var sb = 0.0
        var n = 0
        var y = t
        while (y < b) {
            var x = l
            while (x < rgt) {
                val p = frame.getPixel(x, y)
                sr += Color.red(p)
                sg += Color.green(p)
                sb += Color.blue(p)
                n++
                x += 4
            }
            y += 4
        }
        if (n == 0) return floatArrayOf(0f, 0f, 0f)
        return floatArrayOf((sr / n).toFloat(), (sg / n).toFloat(), (sb / n).toFloat())
    }

    fun luminance(rgb: FloatArray): Float = 0.299f * rgb[0] + 0.587f * rgb[1] + 0.114f * rgb[2]

    /** Colour share of each channel (r, g, b each divided by r+g+b). */
    fun chroma(rgb: FloatArray): FloatArray {
        val s = rgb[0] + rgb[1] + rgb[2] + 1e-6f
        return floatArrayOf(rgb[0] / s, rgb[1] / s, rgb[2] / s)
    }
}
