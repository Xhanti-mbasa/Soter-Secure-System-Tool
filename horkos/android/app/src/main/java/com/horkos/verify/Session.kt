package com.horkos.verify

import android.graphics.Bitmap
import android.graphics.Rect

/** One captured pose from the live face scan. Analysis fields are filled in when Verify runs. */
class Keyframe(
    val label: String,
    val frame: Bitmap,
    val box: Rect,
    val yaw: Float,
    val pitch: Float,
    val roll: Float,
    val leftEye: Float,
    val rightEye: Float,
    val sizeRatio: Float,
    val timeMs: Long
) {
    var mesh: List<FloatArray>? = null
    var parallax: Float? = null
    var similarity: Float? = null
    var spoof: Float? = null
    var embedding: FloatArray? = null
}

/** A frame captured while the screen showed one colour. */
class FlashSample(val color: String, val rgb: FloatArray, val frame: Bitmap, val box: Rect)

class LivenessResult(val completed: Boolean, val steps: List<String>, val message: String)

/** In-memory state for one verification attempt. Nothing is written to disk. */
object Session {
    var frontImage: Bitmap? = null
    var cardFace: Bitmap? = null
    var ocrFront: IdDetails? = null
    var backImage: Bitmap? = null
    var ocrBack: IdDetails? = null
    var barcode: IdDetails? = null
    var code39: String? = null
    var statement: StatementResult? = null
    val keyframes = mutableListOf<Keyframe>()
    val flashes = mutableListOf<FlashSample>()
    var liveness: LivenessResult? = null
    var cardFaceMesh: List<FloatArray>? = null
    var cardEmbedding: FloatArray? = null
    var report: String? = null

    fun clearFace() {
        keyframes.clear()
        flashes.clear()
        liveness = null
        report = null
    }

    fun clear() {
        frontImage = null
        cardFace = null
        ocrFront = null
        backImage = null
        ocrBack = null
        barcode = null
        code39 = null
        statement = null
        cardFaceMesh = null
        cardEmbedding = null
        clearFace()
    }
}
