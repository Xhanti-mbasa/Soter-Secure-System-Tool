package com.horkos.verify

import android.graphics.Bitmap
import android.graphics.Typeface
import android.os.Bundle
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.util.Locale

/** Shows every raw input, intermediate value and drawing behind the verification result. */
class InspectorActivity : AppCompatActivity() {

    private lateinit var root: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val scroll = ScrollView(this)
        root = LinearLayout(this)
        root.orientation = LinearLayout.VERTICAL
        root.setPadding(24, 24, 24, 24)
        scroll.addView(root)
        setContentView(scroll)
        build(
            intent.getStringExtra("id").orEmpty(),
            intent.getStringExtra("names").orEmpty(),
            intent.getStringExtra("surname").orEmpty()
        )
    }

    private fun f(x: Float?, d: Int = 2): String = if (x == null) "-" else String.format(Locale.ROOT, "%.${d}f", x)

    private fun h(s: String) {
        val v = TextView(this)
        v.text = s
        v.textSize = 18f
        v.setTypeface(null, Typeface.BOLD)
        v.setPadding(0, 40, 0, 8)
        root.addView(v)
    }

    private fun t(s: String, mono: Boolean = true) {
        val v = TextView(this)
        v.text = s
        v.textSize = 12f
        if (mono) v.typeface = Typeface.MONOSPACE
        v.setTextIsSelectable(true)
        v.setPadding(0, 4, 0, 4)
        root.addView(v)
    }

    private fun img(b: Bitmap?, heightDp: Int = 260) {
        if (b == null) return
        val v = ImageView(this)
        v.setImageBitmap(b)
        v.adjustViewBounds = true
        v.scaleType = ImageView.ScaleType.FIT_CENTER
        v.layoutParams = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            (heightDp * resources.displayMetrics.density).toInt()
        )
        root.addView(v)
    }

    private fun build(id: String, names: String, surname: String) {
        h("1. Verification report")
        t(Session.report ?: "Tap Verify first.", false)

        h("2. ID number maths")
        t(SaId.explain(id))

        h("3. Barcodes (back of card)")
        t("Code 39 raw: ${Session.code39 ?: "not read"}")
        val bc = Session.barcode
        if (bc == null) {
            t("PDF417 not read")
        } else {
            t("PDF417 raw fields (split on '|'):\n" + bc.raw.split('|').mapIndexed { i, v -> "[$i] $v" }.joinToString("\n"))
            t("Parsed:\n" + bc.summary())
        }

        h("4. ID front (photo + OCR)")
        img(Session.frontImage, 220)
        val front = Session.ocrFront
        t("Parsed:\n" + (front?.summary() ?: "not captured"))
        t("Raw OCR text:\n" + (front?.raw ?: "-"))
        val cf = Session.cardFace
        if (cf != null) {
            t("ID photo with face mesh:", false)
            img(FaceAnalysis.drawMesh(cf, Session.cardFaceMesh, null), 220)
            t("Mesh points: ${Session.cardFaceMesh?.size ?: 0}   nose parallax ${f(FaceAnalysis.parallax(Session.cardFaceMesh), 3)}")
            Session.cardEmbedding?.let { e -> t("ID embedding[0..7] " + e.take(8).joinToString(" ") { v -> f(v, 3) }) }
        }

        h("5. ID back (photo + OCR)")
        img(Session.backImage, 220)
        val back = Session.ocrBack
        t("Card number read: ${back?.cardNumber ?: "-"}   Date of issue read: ${back?.issueDate ?: "-"}")
        t("Raw OCR text:\n" + (back?.raw ?: "-"))

        h("6. Proof of account")
        val st = Session.statement
        if (st == null) {
            t("Not uploaded", false)
        } else {
            t(st.summary())
            st.error?.let { t("Error: $it") }
            val (ok, detail) = StatementCheck.nameMatch(st.text, names, surname)
            t("Name match: " + (if (ok) "YES" else "NO") + " - " + detail)
            t("Red flags:\n" + st.redFlags().joinToString("\n").ifEmpty { "none" })
            t("Extracted text (first 2000 chars):\n" + st.text.take(2000))
        }

        h("7. Face scan keyframes")
        t("Green = 468-point face mesh. Red = nose tip + cheek anchors used for the 3D parallax test. Yellow = detected face box.", false)
        val lv = Session.liveness
        t(if (lv == null) "Face scan not done" else "Result: " + lv.message + "\nSteps: " + lv.steps.joinToString(" > "))
        if (Session.keyframes.isNotEmpty() && Session.keyframes.all { it.mesh == null }) {
            t("Tap Verify to compute the meshes and scores.", false)
        }
        for (k in Session.keyframes) {
            img(FaceAnalysis.drawMesh(k.frame, k.mesh, k.box), 240)
            t(buildString {
                appendLine("${k.label}   t=${k.timeMs} ms")
                appendLine("yaw ${f(k.yaw, 1)}  pitch ${f(k.pitch, 1)}  roll ${f(k.roll, 1)}")
                appendLine("eyes open L ${f(k.leftEye)} R ${f(k.rightEye)}   face width ${f(k.sizeRatio)} of frame")
                appendLine("mesh points ${k.mesh?.size ?: 0}   nose parallax ${f(k.parallax, 3)}   nose depth vs cheeks ${f(FaceAnalysis.noseDepth(k.mesh), 1)}")
                appendLine("similarity to ID photo ${f(k.similarity)}   spoof score ${f(k.spoof, 3)}")
                k.embedding?.let { e -> appendLine("embedding[0..7] " + e.take(8).joinToString(" ") { v -> f(v, 3) }) }
            }.trim())
        }

        h("8. Screen-flash test")
        t("Mean colour of the face while the screen showed each colour. A real face near the screen picks up the colour.", false)
        for (s in Session.flashes) {
            img(ImageUtils.cropFace(s.frame, s.box, 0.2f), 120)
            val ch = FaceAnalysis.chroma(s.rgb)
            t("${s.color}: RGB " + s.rgb.joinToString(" ") { v -> f(v, 0) } + "   share r/g/b " + ch.joinToString(" ") { v -> f(v, 3) })
        }
    }
}
