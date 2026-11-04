package com.horkos.verify

import android.app.Activity
import android.hardware.camera2.CaptureRequest
import androidx.annotation.OptIn
import androidx.camera.camera2.interop.Camera2CameraControl
import androidx.camera.camera2.interop.CaptureRequestOptions
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.Camera
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Rect
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Size
import android.view.View
import android.view.WindowManager
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.abs

/**
 * Guided live face scan: oval guide, randomised head poses, distance changes, blink,
 * then full-screen colour flashes. A keyframe is captured for every completed step.
 */
class LivenessActivity : AppCompatActivity() {

    private enum class Step(val prompt: String) {
        CENTER("Fit your face inside the oval"),
        LEFT("Slowly turn your head LEFT"),
        RIGHT("Slowly turn your head RIGHT"),
        UP("Tilt your head UP"),
        DOWN("Tilt your head DOWN"),
        CLOSER("Bring the phone CLOSER to your face"),
        FARTHER("Move the phone FURTHER away"),
        BLINK("Blink slowly"),
        FINAL("Look straight at the camera"),
        FLASH("Hold still - the screen will flash colours")
    }

    private lateinit var previewView: PreviewView
    private lateinit var overlay: OvalOverlayView
    private lateinit var tvInstruction: TextView
    private lateinit var tvProgress: TextView
    private lateinit var flashView: View
    private lateinit var executor: ExecutorService
    private val main = Handler(Looper.getMainLooper())
    private val finished = AtomicBoolean(false)
    private var camera: Camera? = null

    private val detector by lazy {
        FaceDetection.getClient(
            FaceDetectorOptions.Builder()
                .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
                .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_ALL)
                .setMinFaceSize(0.15f)
                .build()
        )
    }

    private lateinit var steps: List<Step>
    @Volatile private var index = 0
    private var holdFrames = 0
    private var yawSign = 0f
    private var pitchSign = 0f
    private var baseSize = 0f
    private var eyesWereOpen = false
    private var lastBox: Rect? = null
    private val startedAt = SystemClock.elapsedRealtime()
    private val completedSteps = mutableListOf<String>()

    private val flashSequence = listOf(
        "BASELINE" to Color.TRANSPARENT,
        "WHITE" to Color.WHITE,
        "RED" to Color.RED,
        "GREEN" to Color.GREEN,
        "BLUE" to Color.BLUE
    )
    @Volatile private var flashColor: String? = null
    @Volatile private var flashSetAt = 0L
    private val flashCaptured = mutableSetOf<String>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_liveness)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.attributes = window.attributes.apply { screenBrightness = 1f }
        previewView = findViewById(R.id.previewView)
        overlay = findViewById(R.id.overlay)
        tvInstruction = findViewById(R.id.tvInstruction)
        tvProgress = findViewById(R.id.tvProgress)
        flashView = findViewById(R.id.flashView)
        executor = Executors.newSingleThreadExecutor()

        val pairs = listOf(listOf(Step.LEFT, Step.RIGHT).shuffled(), listOf(Step.UP, Step.DOWN).shuffled()).shuffled()
        steps = listOf(Step.CENTER) + pairs.flatten() + listOf(Step.CLOSER, Step.FARTHER).shuffled() +
            listOf(Step.BLINK, Step.FINAL, Step.FLASH)
        Session.clearFace()
        showStep()
        startCamera()
    }

    override fun onDestroy() {
        super.onDestroy()
        finished.set(true)
        main.removeCallbacksAndMessages(null)
        executor.shutdown()
    }

    private fun startCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            val provider = future.get()
            val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
            val resolution = ResolutionSelector.Builder()
                .setResolutionStrategy(ResolutionStrategy(Size(640, 480), ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER))
                .build()
            val analysis = ImageAnalysis.Builder()
                .setResolutionSelector(resolution)
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                .build()
            analysis.setAnalyzer(executor) { proxy -> analyse(proxy) }
            provider.unbindAll()
            try {
                camera = provider.bindToLifecycle(this, CameraSelector.DEFAULT_FRONT_CAMERA, preview, analysis)
            } catch (e: Exception) {
                Toast.makeText(this, "Camera error: ${e.message}", Toast.LENGTH_LONG).show()
                finish()
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun showStep() {
        val i = index
        main.post {
            tvInstruction.text = steps[i].prompt
            tvProgress.text = "Step ${i + 1} of ${steps.size}"
        }
    }

    private fun hint(msg: String, color: Int) {
        main.post {
            tvInstruction.text = msg
            overlay.ovalColor = color
        }
    }

    private fun analyse(proxy: ImageProxy) {
        if (finished.get()) {
            proxy.close()
            return
        }
        val frame: Bitmap
        try {
            frame = ImageUtils.rotate(proxy.toBitmap(), proxy.imageInfo.rotationDegrees)
        } catch (e: Exception) {
            proxy.close()
            return
        }
        proxy.close()

        val step = steps[index]
        if (SystemClock.elapsedRealtime() - startedAt > 120_000) {
            complete(false, "Timed out at step ${step.name}")
            return
        }
        if (step == Step.FLASH) {
            handleFlash(frame)
            return
        }

        val faces = try {
            Tasks.await(detector.process(InputImage.fromBitmap(frame, 0)))
        } catch (e: Exception) {
            return
        }
        if (faces.isEmpty()) {
            holdFrames = 0
            hint("No face found - look at the screen", Color.RED)
            return
        }
        if (faces.size > 1) {
            holdFrames = 0
            hint("Only one face, please", Color.RED)
            return
        }
        val face = faces[0]
        val box = face.boundingBox
        lastBox = Rect(box)
        val size = box.width().toFloat() / frame.width
        val cx = box.exactCenterX() / frame.width
        val cy = box.exactCenterY() / frame.height
        val sizeStep = step == Step.CLOSER || step == Step.FARTHER

        if (cx < 0.25f || cx > 0.75f || cy < 0.2f || cy > 0.75f) {
            holdFrames = 0
            hint("Centre your face in the oval", Color.YELLOW)
            return
        }
        if (!sizeStep && size < 0.28f) {
            holdFrames = 0
            hint("Come a bit closer", Color.YELLOW)
            return
        }
        if (!sizeStep && size > 0.85f) {
            holdFrames = 0
            hint("Move the phone back a bit", Color.YELLOW)
            return
        }
        if (FaceAnalysis.luminance(FaceAnalysis.meanRgb(frame, box)) < 45f) {
            holdFrames = 0
            hint("Too dark - face a light source", Color.YELLOW)
            return
        }
        hint(step.prompt, Color.WHITE)

        val yaw = face.headEulerAngleY
        val pitch = face.headEulerAngleX
        val l = face.leftEyeOpenProbability ?: -1f
        val r = face.rightEyeOpenProbability ?: -1f
        val eyesOpen = l > 0.6f && r > 0.6f
        val eyesClosed = l in 0f..0.3f && r in 0f..0.3f

        val met = when (step) {
            Step.CENTER, Step.FINAL -> abs(yaw) < 10 && abs(pitch) < 10 && eyesOpen
            Step.LEFT, Step.RIGHT -> abs(pitch) < 20 && (if (yawSign == 0f) abs(yaw) > 22 else yaw * yawSign < -22)
            Step.UP, Step.DOWN -> abs(yaw) < 20 && (if (pitchSign == 0f) abs(pitch) > 14 else pitch * pitchSign < -14)
            Step.CLOSER -> baseSize > 0f && size > baseSize * 1.3f && abs(yaw) < 15
            Step.FARTHER -> baseSize > 0f && size < baseSize * 0.75f && abs(yaw) < 15
            Step.BLINK -> {
                if (eyesOpen) eyesWereOpen = true
                eyesWereOpen && eyesClosed
            }
            Step.FLASH -> false
        }
        if (!met) {
            holdFrames = 0
            return
        }
        holdFrames++
        val needed = if (step == Step.BLINK) 1 else 3
        if (holdFrames < needed) return
        holdFrames = 0

        when (step) {
            Step.CENTER -> baseSize = size
            Step.LEFT, Step.RIGHT -> if (yawSign == 0f) yawSign = if (yaw > 0) 1f else -1f
            Step.UP, Step.DOWN -> if (pitchSign == 0f) pitchSign = if (pitch > 0) 1f else -1f
            else -> {}
        }
        Session.keyframes.add(
            Keyframe(
                step.name, frame, Rect(box), yaw, pitch, face.headEulerAngleZ, l, r, size,
                SystemClock.elapsedRealtime() - startedAt
            )
        )
        completedSteps.add(step.name)
        main.post { overlay.ovalColor = Color.GREEN }
        index++
        if (steps[index] == Step.FLASH) main.postDelayed({ runFlash(0) }, 800)
        showStep()
    }

    private fun runFlash(i: Int) {
        if (finished.get()) return
        if (i == 0) lock3A(true)
        if (i >= flashSequence.size) {
            lock3A(false)
            flashView.visibility = View.GONE
            complete(true, "All challenges completed")
            return
        }
        val (name, color) = flashSequence[i]
        if (color == Color.TRANSPARENT) {
            flashView.visibility = View.GONE
        } else {
            flashView.setBackgroundColor(color)
            flashView.visibility = View.VISIBLE
        }
        flashSetAt = SystemClock.elapsedRealtime()
        flashColor = name
        main.postDelayed({ runFlash(i + 1) }, 900)
    }

    /** Locks auto-exposure and auto-white-balance so the camera does not cancel out the flash colours. */
    @OptIn(ExperimentalCamera2Interop::class)
    private fun lock3A(lock: Boolean) {
        val cam = camera ?: return
        try {
            Camera2CameraControl.from(cam.cameraControl).setCaptureRequestOptions(
                CaptureRequestOptions.Builder()
                    .setCaptureRequestOption(CaptureRequest.CONTROL_AE_LOCK, lock)
                    .setCaptureRequestOption(CaptureRequest.CONTROL_AWB_LOCK, lock)
                    .build()
            )
        } catch (e: Exception) {
        }
    }

    private fun handleFlash(frame: Bitmap) {
        val name = flashColor ?: return
        if (name in flashCaptured) return
        if (SystemClock.elapsedRealtime() - flashSetAt < 450) return
        val box = lastBox ?: return
        flashCaptured.add(name)
        val bg = FaceAnalysis.meanRgbRect(frame, Rect(0, 0, frame.width, frame.height / 6))
        Session.flashes.add(FlashSample(name, FaceAnalysis.meanRgb(frame, box), frame, Rect(box), bg))
    }

    private fun complete(ok: Boolean, msg: String) {
        if (!finished.compareAndSet(false, true)) return
        Session.liveness = LivenessResult(ok, completedSteps.toList(), msg)
        main.post {
            if (!ok) Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
            setResult(Activity.RESULT_OK)
            finish()
        }
    }
}
