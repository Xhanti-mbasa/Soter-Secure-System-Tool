package com.horkos.verify

import android.app.Activity
import android.graphics.Bitmap
import android.os.Bundle
import android.os.SystemClock
import android.util.Size
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.android.gms.tasks.Tasks
import com.google.android.material.button.MaterialButton
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/** Camera screen for the ID card: FRONT (photo + OCR + face crop) or BACK (both barcodes + OCR). */
class ScanActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_MODE = "mode"
        const val MODE_FRONT = "front"
        const val MODE_BACK = "back"
    }

    private lateinit var previewView: PreviewView
    private lateinit var instruction: TextView
    private lateinit var captureButton: MaterialButton
    private lateinit var executor: ExecutorService
    private val done = AtomicBoolean(false)
    private var imageCapture: ImageCapture? = null
    private lateinit var mode: String

    // Back-of-card state (only touched on the analysis thread)
    private var pdfRaw: String? = null
    private var pdfFoundAt = 0L
    private var pdfFrame: Bitmap? = null
    private var code39Raw: String? = null

    private val recognizer by lazy { TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS) }
    private val scanner by lazy {
        BarcodeScanning.getClient(
            BarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_PDF417, Barcode.FORMAT_CODE_39).build()
        )
    }
    private val faceDetector by lazy {
        FaceDetection.getClient(
            FaceDetectorOptions.Builder()
                .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_ACCURATE)
                .setMinFaceSize(0.05f)
                .build()
        )
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_scan)
        previewView = findViewById(R.id.previewView)
        instruction = findViewById(R.id.tvInstruction)
        captureButton = findViewById(R.id.btnCapture)
        executor = Executors.newSingleThreadExecutor()
        mode = intent.getStringExtra(EXTRA_MODE) ?: MODE_FRONT

        if (mode == MODE_FRONT) {
            instruction.text = "Fit the FRONT of the ID in the frame, then tap Capture"
            captureButton.visibility = View.VISIBLE
            captureButton.setOnClickListener { captureFront() }
        } else {
            instruction.text = "Point at the barcodes on the BACK of the ID"
        }
        startCamera()
    }

    override fun onDestroy() {
        super.onDestroy()
        executor.shutdown()
    }

    private fun startCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            val provider = future.get()
            val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
            val resolution = ResolutionSelector.Builder()
                .setResolutionStrategy(ResolutionStrategy(Size(1920, 1080), ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER))
                .build()
            provider.unbindAll()
            try {
                if (mode == MODE_FRONT) {
                    val capture = ImageCapture.Builder()
                        .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                        .setResolutionSelector(resolution)
                        .build()
                    imageCapture = capture
                    provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, capture)
                } else {
                    val analysis = ImageAnalysis.Builder()
                        .setResolutionSelector(resolution)
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                        .build()
                    analysis.setAnalyzer(executor) { proxy -> analyseBack(proxy) }
                    provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
                }
            } catch (e: Exception) {
                Toast.makeText(this, "Camera error: ${e.message}", Toast.LENGTH_LONG).show()
                finish()
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun say(msg: String) = runOnUiThread { instruction.text = msg }

    private fun finishOk() {
        runOnUiThread {
            setResult(Activity.RESULT_OK)
            finish()
        }
    }

    // ---------------- Back: both barcodes + printed card number / issue date ----------------

    private fun analyseBack(proxy: ImageProxy) {
        if (done.get()) {
            proxy.close()
            return
        }
        val bmp: Bitmap
        try {
            bmp = ImageUtils.rotate(proxy.toBitmap(), proxy.imageInfo.rotationDegrees)
        } catch (e: Exception) {
            proxy.close()
            return
        }
        proxy.close()
        val codes = try {
            Tasks.await(scanner.process(InputImage.fromBitmap(bmp, 0)))
        } catch (e: Exception) {
            return
        }
        for (c in codes) {
            val raw = c.rawValue ?: continue
            if (c.format == Barcode.FORMAT_PDF417 && pdfRaw == null) {
                pdfRaw = raw
                pdfFoundAt = SystemClock.elapsedRealtime()
                pdfFrame = bmp
            }
            if (c.format == Barcode.FORMAT_CODE_39 && code39Raw == null) code39Raw = raw
        }
        val pdf = pdfRaw
        if (pdf == null) {
            say(if (code39Raw != null) "Small barcode read. Now show the BIG barcode" else "Point at the barcodes on the BACK of the ID")
            return
        }
        if (code39Raw == null && SystemClock.elapsedRealtime() - pdfFoundAt < 4000) {
            say("Big barcode read. Hold still so the small barcode is also visible...")
            return
        }
        if (!done.compareAndSet(false, true)) return
        say("Reading the back of the card...")
        val frame = pdfFrame ?: bmp
        val text = try {
            Tasks.await(recognizer.process(InputImage.fromBitmap(frame, 0)))
        } catch (e: Exception) {
            null
        }
        val parsed = BarcodeParser.parse(pdf)
        Session.barcode = parsed
        Session.code39 = code39Raw
        Session.backImage = ImageUtils.downscale(frame, 1600)
        if (text != null) {
            Session.ocrBack = OcrParser.parse(text, "OCR (back of card)")
                .copy(cardNumber = OcrParser.cardNumber(text.text, parsed.idNumber))
        }
        finishOk()
    }

    // ---------------- Front: photo, OCR, ID photo crop ----------------

    private fun captureFront() {
        val capture = imageCapture ?: return
        captureButton.isEnabled = false
        instruction.text = "Reading card..."
        capture.takePicture(executor, object : ImageCapture.OnImageCapturedCallback() {
            override fun onCaptureSuccess(image: ImageProxy) {
                val bmp = try {
                    ImageUtils.downscale(ImageUtils.rotate(image.toBitmap(), image.imageInfo.rotationDegrees), 2000)
                } finally {
                    image.close()
                }
                processFront(bmp)
            }

            override fun onError(exception: ImageCaptureException) {
                runOnUiThread {
                    captureButton.isEnabled = true
                    instruction.text = "Capture failed, try again"
                }
            }
        })
    }

    private fun processFront(bmp: Bitmap) {
        try {
            val input = InputImage.fromBitmap(bmp, 0)
            val text = Tasks.await(recognizer.process(input))
            val faces = Tasks.await(faceDetector.process(input))
            Session.ocrFront = OcrParser.parse(text)
            Session.frontImage = ImageUtils.downscale(bmp, 1600)
            val face = faces.maxByOrNull { it.boundingBox.width() * it.boundingBox.height() }
            Session.cardFace = face?.let { ImageUtils.cropFace(bmp, it.boundingBox, 0.3f) }
            Session.cardFaceMesh = null
            Session.cardEmbedding = null
            if (face == null) {
                runOnUiThread { Toast.makeText(this, "Text read, but no face found on the card", Toast.LENGTH_LONG).show() }
            }
            finishOk()
        } catch (e: Exception) {
            runOnUiThread {
                captureButton.isEnabled = true
                instruction.text = "Could not read the card: ${e.message}"
            }
        }
    }
}
