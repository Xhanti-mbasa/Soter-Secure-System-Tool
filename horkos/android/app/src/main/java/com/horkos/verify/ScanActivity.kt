package com.horkos.verify

import android.app.Activity
import android.graphics.Bitmap
import android.os.Bundle
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
import com.google.android.material.button.MaterialButton
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.Face
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.abs

/** One camera screen with three modes: barcode scan, ID-card capture, live selfie. */
class ScanActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_MODE = "mode"
        const val MODE_BARCODE = "barcode"
        const val MODE_CARD = "card"
        const val MODE_SELFIE = "selfie"
    }

    private lateinit var previewView: PreviewView
    private lateinit var instruction: TextView
    private lateinit var captureButton: MaterialButton
    private lateinit var executor: ExecutorService
    private val done = AtomicBoolean(false)
    private var imageCapture: ImageCapture? = null
    private lateinit var mode: String

    // Selfie liveness state
    private enum class Step { FIND_FACE, BLINK, TURN, CENTER }
    @Volatile private var step = Step.FIND_FACE
    private var eyesWereOpen = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_scan)
        previewView = findViewById(R.id.previewView)
        instruction = findViewById(R.id.tvInstruction)
        captureButton = findViewById(R.id.btnCapture)
        executor = Executors.newSingleThreadExecutor()
        mode = intent.getStringExtra(EXTRA_MODE) ?: MODE_BARCODE

        instruction.text = when (mode) {
            MODE_BARCODE -> "Point at the large barcode on the BACK of the ID"
            MODE_CARD -> "Fit the FRONT of the ID in the frame, then tap Capture"
            else -> "Look straight at the camera"
        }
        if (mode == MODE_CARD) {
            captureButton.visibility = View.VISIBLE
            captureButton.setOnClickListener { captureCard() }
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
            val selector = if (mode == MODE_SELFIE) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA

            val targetSize = if (mode == MODE_SELFIE) Size(640, 480) else Size(1920, 1080)
            val resolution = ResolutionSelector.Builder()
                .setResolutionStrategy(ResolutionStrategy(targetSize, ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER))
                .build()

            provider.unbindAll()
            try {
                if (mode == MODE_CARD) {
                    val capture = ImageCapture.Builder()
                        .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                        .setResolutionSelector(resolution)
                        .build()
                    imageCapture = capture
                    provider.bindToLifecycle(this, selector, preview, capture)
                } else {
                    val analysis = ImageAnalysis.Builder()
                        .setResolutionSelector(resolution)
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                        .build()
                    analysis.setAnalyzer(executor) { proxy ->
                        if (mode == MODE_BARCODE) analyseBarcode(proxy) else analyseSelfie(proxy)
                    }
                    provider.bindToLifecycle(this, selector, preview, analysis)
                }
            } catch (e: Exception) {
                Toast.makeText(this, "Camera error: ${e.message}", Toast.LENGTH_LONG).show()
                finish()
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun frameBitmap(proxy: ImageProxy): Bitmap =
        ImageUtils.rotate(proxy.toBitmap(), proxy.imageInfo.rotationDegrees)

    private fun finishOk() {
        runOnUiThread {
            setResult(Activity.RESULT_OK)
            finish()
        }
    }

    // ---------------- Barcode ----------------

    private val barcodeScanner by lazy {
        BarcodeScanning.getClient(
            BarcodeScannerOptions.Builder()
                .setBarcodeFormats(Barcode.FORMAT_PDF417, Barcode.FORMAT_CODE_39)
                .build()
        )
    }

    private fun analyseBarcode(proxy: ImageProxy) {
        if (done.get()) { proxy.close(); return }
        val bmp = try { frameBitmap(proxy) } catch (e: Exception) { proxy.close(); return }
        proxy.close()
        barcodeScanner.process(InputImage.fromBitmap(bmp, 0))
            .addOnSuccessListener { codes ->
                // Prefer the PDF417 (full details) over Code 39 (ID number only)
                val code = codes.firstOrNull { it.format == Barcode.FORMAT_PDF417 && !it.rawValue.isNullOrBlank() }
                    ?: codes.firstOrNull { !it.rawValue.isNullOrBlank() }
                val raw = code?.rawValue ?: return@addOnSuccessListener
                if (done.compareAndSet(false, true)) {
                    Session.barcode = BarcodeParser.parse(raw)
                    finishOk()
                }
            }
    }

    // ---------------- ID card front ----------------

    private fun captureCard() {
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
                processCard(bmp)
            }

            override fun onError(exception: ImageCaptureException) {
                runOnUiThread {
                    captureButton.isEnabled = true
                    instruction.text = "Capture failed, try again"
                }
            }
        })
    }

    private fun processCard(bmp: Bitmap) {
        val input = InputImage.fromBitmap(bmp, 0)
        val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        val faceDetector = FaceDetection.getClient(
            FaceDetectorOptions.Builder()
                .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_ACCURATE)
                .setMinFaceSize(0.05f)
                .build()
        )
        recognizer.process(input)
            .addOnSuccessListener { text ->
                Session.ocr = OcrParser.parse(text)
                faceDetector.process(input)
                    .addOnSuccessListener { faces ->
                        val face = faces.maxByOrNull { it.boundingBox.width() * it.boundingBox.height() }
                        if (face != null) {
                            Session.cardFace = ImageUtils.cropFace(bmp, face.boundingBox)
                        } else {
                            Toast.makeText(this, "Text read, but no face found on the card", Toast.LENGTH_LONG).show()
                        }
                        finishOk()
                    }
                    .addOnFailureListener { finishOk() }
            }
            .addOnFailureListener {
                captureButton.isEnabled = true
                instruction.text = "Could not read the card, try again"
            }
    }

    // ---------------- Live selfie ----------------

    private val selfieDetector by lazy {
        FaceDetection.getClient(
            FaceDetectorOptions.Builder()
                .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
                .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_ALL)
                .setMinFaceSize(0.25f)
                .build()
        )
    }

    private fun say(msg: String) = runOnUiThread { instruction.text = msg }

    private fun analyseSelfie(proxy: ImageProxy) {
        if (done.get()) { proxy.close(); return }
        val bmp = try { frameBitmap(proxy) } catch (e: Exception) { proxy.close(); return }
        proxy.close()
        selfieDetector.process(InputImage.fromBitmap(bmp, 0))
            .addOnSuccessListener { faces ->
                if (faces.size != 1) {
                    say(if (faces.isEmpty()) "No face found - look at the camera" else "Only one person, please")
                    return@addOnSuccessListener
                }
                handleSelfieFace(faces[0], bmp)
            }
    }

    private fun handleSelfieFace(face: Face, bmp: Bitmap) {
        val left = face.leftEyeOpenProbability ?: -1f
        val right = face.rightEyeOpenProbability ?: -1f
        val yaw = face.headEulerAngleY
        val eyesOpen = left > 0.7f && right > 0.7f
        val eyesClosed = left in 0f..0.3f && right in 0f..0.3f

        when (step) {
            Step.FIND_FACE -> {
                if (abs(yaw) < 12) { step = Step.BLINK; say("Blink slowly") }
                else say("Face the camera straight on")
            }
            Step.BLINK -> {
                if (eyesOpen) eyesWereOpen = true
                if (eyesWereOpen && eyesClosed) {
                    Session.blinkPassed = true
                    step = Step.TURN
                    say("Now turn your head to the side")
                }
            }
            Step.TURN -> {
                if (abs(yaw) > 25) {
                    Session.turnPassed = true
                    step = Step.CENTER
                    say("Great - look straight at the camera again")
                }
            }
            Step.CENTER -> {
                if (abs(yaw) < 8 && eyesOpen && done.compareAndSet(false, true)) {
                    Session.selfieFace = ImageUtils.cropFace(bmp, face.boundingBox)
                    say("Done")
                    finishOk()
                }
            }
        }
    }
}
