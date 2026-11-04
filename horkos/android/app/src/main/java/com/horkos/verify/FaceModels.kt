package com.horkos.verify

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.graphics.Rect
import org.tensorflow.lite.Interpreter
import java.io.FileInputStream
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

object ImageUtils {
    fun rotate(src: Bitmap, degrees: Int): Bitmap {
        if (degrees % 360 == 0) return src
        val m = Matrix().apply { postRotate(degrees.toFloat()) }
        return Bitmap.createBitmap(src, 0, 0, src.width, src.height, m, true)
    }

    fun downscale(src: Bitmap, maxSide: Int): Bitmap {
        val longest = max(src.width, src.height)
        if (longest <= maxSide) return src
        val s = maxSide.toFloat() / longest
        return Bitmap.createScaledBitmap(src, (src.width * s).toInt(), (src.height * s).toInt(), true)
    }

    /** Square crop around a face box with some margin, clamped to the image. */
    fun cropFace(src: Bitmap, box: Rect, margin: Float = 0.2f): Bitmap {
        val size = (max(box.width(), box.height()) * (1 + 2 * margin)).toInt()
        val cx = box.centerX()
        val cy = box.centerY()
        var left = cx - size / 2
        var top = cy - size / 2
        left = left.coerceIn(0, max(0, src.width - 1))
        top = top.coerceIn(0, max(0, src.height - 1))
        val w = min(size, src.width - left)
        val h = min(size, src.height - top)
        return Bitmap.createBitmap(src, left, top, max(1, w), max(1, h))
    }
}

/**
 * MobileFaceNet (face embeddings) + FaceAntiSpoofing (passive liveness) TFLite models.
 * Models: github.com/syaringan357/Android-MobileFaceNet-MTCNN-FaceAntiSpoofing (MIT).
 */
class FaceModels(context: Context) {

    private val faceNet = Interpreter(load(context, "MobileFaceNet.tflite"), Interpreter.Options().setNumThreads(4))
    private val antiSpoof = Interpreter(load(context, "FaceAntiSpoofing.tflite"), Interpreter.Options().setNumThreads(4))

    private fun load(context: Context, name: String): MappedByteBuffer {
        val fd = context.assets.openFd(name)
        FileInputStream(fd.fileDescriptor).use { stream ->
            return stream.channel.map(FileChannel.MapMode.READ_ONLY, fd.startOffset, fd.declaredLength)
        }
    }

    private fun toInput(bitmap: Bitmap, size: Int, mean: Float, std: Float): Array<Array<FloatArray>> {
        val b = Bitmap.createScaledBitmap(bitmap, size, size, true)
        val px = IntArray(size * size)
        b.getPixels(px, 0, size, 0, 0, size, size)
        return Array(size) { y ->
            Array(size) { x ->
                val v = px[y * size + x]
                floatArrayOf(
                    (((v shr 16) and 0xFF) - mean) / std,
                    (((v shr 8) and 0xFF) - mean) / std,
                    ((v and 0xFF) - mean) / std
                )
            }
        }
    }

    /** Cosine similarity (-1..1) between the faces in two crops. Higher = more alike. */
    @Synchronized
    fun similarity(face1: Bitmap, face2: Bitmap): Float {
        val inShape = faceNet.getInputTensor(0).shape()     // expected [2,112,112,3]
        val size = inShape[1]
        val batch = inShape[0]
        val dim = faceNet.getOutputTensor(0).shape()[1]
        val a = toInput(face1, size, 127.5f, 128f)
        val b = toInput(face2, size, 127.5f, 128f)

        val e1: FloatArray
        val e2: FloatArray
        if (batch >= 2) {
            val input = Array(batch) { i -> if (i == 0) a else b }
            val out = Array(batch) { FloatArray(dim) }
            faceNet.run(input, out)
            e1 = out[0]; e2 = out[1]
        } else {
            val o1 = Array(1) { FloatArray(dim) }
            val o2 = Array(1) { FloatArray(dim) }
            faceNet.run(arrayOf(a), o1)
            faceNet.run(arrayOf(b), o2)
            e1 = o1[0]; e2 = o2[0]
        }
        return cosine(e1, e2)
    }

    private fun cosine(a: FloatArray, b: FloatArray): Float {
        var dot = 0f; var na = 0f; var nb = 0f
        for (i in a.indices) {
            dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]
        }
        return dot / (sqrt(na) * sqrt(nb) + 1e-10f)
    }

    /** Spoof score: below [SPOOF_THRESHOLD] looks like a real face, above looks like a photo/screen. */
    @Synchronized
    fun spoofScore(face: Bitmap): Float {
        val size = antiSpoof.getInputTensor(0).shape()[1]
        val input = arrayOf(toInput(face, size, 0f, 255f))
        val clss = Array(1) { FloatArray(8) }
        val mask = Array(1) { FloatArray(8) }
        val iClss = runCatching { antiSpoof.getOutputIndex("Identity") }.getOrDefault(0)
        val iMask = runCatching { antiSpoof.getOutputIndex("Identity_1") }.getOrDefault(1)
        antiSpoof.runForMultipleInputsOutputs(arrayOf<Any>(input), mapOf<Int, Any>(iClss to clss, iMask to mask))
        var score = 0f
        for (i in 0 until 8) score += kotlin.math.abs(clss[0][i]) * mask[0][i]
        return score
    }

    companion object {
        const val SPOOF_THRESHOLD = 0.2f
        const val MATCH_THRESHOLD = 0.55f

        @Volatile private var instance: FaceModels? = null
        fun get(context: Context): FaceModels =
            instance ?: synchronized(this) {
                instance ?: FaceModels(context.applicationContext).also { instance = it }
            }
    }
}
