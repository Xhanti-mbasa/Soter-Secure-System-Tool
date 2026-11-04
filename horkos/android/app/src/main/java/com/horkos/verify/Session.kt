package com.horkos.verify

import android.graphics.Bitmap

/** In-memory state for one verification attempt. Nothing is written to disk. */
object Session {
    var barcode: IdDetails? = null
    var ocr: IdDetails? = null
    var cardFace: Bitmap? = null
    var selfieFace: Bitmap? = null
    var blinkPassed = false
    var turnPassed = false

    fun clear() {
        barcode = null
        ocr = null
        cardFace = null
        selfieFace = null
        blinkPassed = false
        turnPassed = false
    }
}
