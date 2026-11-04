package com.horkos.verify

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import java.time.LocalDate
import java.util.Locale
import java.util.concurrent.Executors
import kotlin.math.abs

class MainActivity : AppCompatActivity() {

    private lateinit var tvFront: TextView
    private lateinit var tvBack: TextView
    private lateinit var tvStatement: TextView
    private lateinit var tvFace: TextView
    private lateinit var tvResults: TextView
    private lateinit var imgCardFace: ImageView
    private lateinit var imgSelfie: ImageView
    private lateinit var etNames: TextInputEditText
    private lateinit var etSurname: TextInputEditText
    private lateinit var etId: TextInputEditText
    private lateinit var etDob: TextInputEditText
    private lateinit var etCountry: TextInputEditText
    private lateinit var spSex: Spinner
    private lateinit var spCitizenship: Spinner
    private lateinit var spMarital: Spinner
    private lateinit var spCriminal: Spinner
    private lateinit var spQualification: Spinner
    private lateinit var btnInspector: MaterialButton
    private lateinit var btnExport: MaterialButton

    private val worker = Executors.newSingleThreadExecutor()
    private var pending: (() -> Unit)? = null

    private val scanLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        refresh()
    }

    private val permissionLauncher = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        val p = pending
        pending = null
        if (granted && p != null) p()
        else if (!granted) Toast.makeText(this, "Camera permission is needed", Toast.LENGTH_LONG).show()
    }

    private val pdfLauncher = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) analyseStatement(uri)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        tvFront = findViewById(R.id.tvFront)
        tvBack = findViewById(R.id.tvBack)
        tvStatement = findViewById(R.id.tvStatement)
        tvFace = findViewById(R.id.tvFace)
        tvResults = findViewById(R.id.tvResults)
        imgCardFace = findViewById(R.id.imgCardFace)
        imgSelfie = findViewById(R.id.imgSelfie)
        etNames = findViewById(R.id.etNames)
        etSurname = findViewById(R.id.etSurname)
        etId = findViewById(R.id.etIdNumber)
        etDob = findViewById(R.id.etDob)
        etCountry = findViewById(R.id.etCountry)
        spSex = findViewById(R.id.spSex)
        spCitizenship = findViewById(R.id.spCitizenship)
        spMarital = findViewById(R.id.spMarital)
        spCriminal = findViewById(R.id.spCriminal)
        spQualification = findViewById(R.id.spQualification)
        btnInspector = findViewById(R.id.btnInspector)

        findViewById<MaterialButton>(R.id.btnFront).setOnClickListener {
            withCamera { scanLauncher.launch(Intent(this, ScanActivity::class.java).putExtra(ScanActivity.EXTRA_MODE, ScanActivity.MODE_FRONT)) }
        }
        findViewById<MaterialButton>(R.id.btnBack).setOnClickListener {
            withCamera { scanLauncher.launch(Intent(this, ScanActivity::class.java).putExtra(ScanActivity.EXTRA_MODE, ScanActivity.MODE_BACK)) }
        }
        findViewById<MaterialButton>(R.id.btnStatement).setOnClickListener { pdfLauncher.launch(arrayOf("application/pdf")) }
        findViewById<MaterialButton>(R.id.btnFace).setOnClickListener {
            withCamera { scanLauncher.launch(Intent(this, LivenessActivity::class.java)) }
        }
        findViewById<MaterialButton>(R.id.btnVerify).setOnClickListener { verify() }
        findViewById<MaterialButton>(R.id.btnReset).setOnClickListener { reset() }
        btnInspector.setOnClickListener { openInspector() }
        btnInspector.isEnabled = false
        btnExport = MaterialButton(this)
        btnExport.text = "Export data (ID number removed)"
        btnExport.isEnabled = false
        btnExport.setOnClickListener { exportData() }
        val parentLayout = btnInspector.parent as LinearLayout
        parentLayout.addView(
            btnExport,
            parentLayout.indexOfChild(btnInspector) + 1,
            LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
        )

        worker.execute { runCatching { FaceModels.get(this) } }
        refresh()
    }

    override fun onDestroy() {
        super.onDestroy()
        worker.shutdown()
    }

    private fun withCamera(action: () -> Unit) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            action()
        } else {
            pending = action
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    private fun analyseStatement(uri: Uri) {
        tvStatement.text = "Analysing statement..."
        val id = etId.text?.toString()?.trim()
        worker.execute {
            val r = try {
                StatementCheck.analyse(this, uri, id)
            } catch (e: Exception) {
                StatementCheck.fail(uri.lastPathSegment ?: "file", "${e.javaClass.simpleName}: ${e.message}")
            }
            Session.statement = r
            runOnUiThread { refresh() }
        }
    }

    private fun refresh() {
        val front = Session.ocrFront
        tvFront.text = front?.summary() ?: "Not captured yet"

        val bc = Session.barcode
        tvBack.text = if (bc == null) "Not captured yet" else buildString {
            appendLine(bc.summary())
            appendLine("Small barcode (Code 39): ${Session.code39 ?: "not read"}")
            Session.ocrBack?.cardNumber?.let { appendLine("Card number (printed): $it") }
            Session.ocrBack?.issueDate?.let { appendLine("Date of issue (printed): $it") }
        }.trim()

        val st = Session.statement
        tvStatement.text = when {
            st == null -> "No statement uploaded"
            st.error != null -> "Error: ${st.error}"
            else -> "${st.bank ?: "Unknown bank"} - ${st.pages} page(s), text via ${st.textSource}. Red flags: ${st.redFlags().size}"
        }

        val lv = Session.liveness
        tvFace.text = if (lv == null) "Not done yet" else
            (if (lv.completed) "Completed: " else "Incomplete: ") + lv.message +
                "\nCaptured ${Session.keyframes.size} poses + ${Session.flashes.size} flash frames"

        imgCardFace.setImageBitmap(Session.cardFace)
        val k = Session.keyframes.lastOrNull { it.label == "FINAL" } ?: Session.keyframes.firstOrNull()
        imgSelfie.setImageBitmap(k?.let { ImageUtils.cropFace(it.frame, it.box) })

        fun fill(et: TextInputEditText, vararg values: String?) {
            if (et.text.isNullOrBlank()) values.firstOrNull { !it.isNullOrBlank() }?.let { et.setText(it) }
        }
        fill(etNames, bc?.names, front?.names)
        fill(etSurname, bc?.surname, front?.surname)
        fill(etId, bc?.idNumber, front?.idNumber)
        fill(etDob, (bc?.dob ?: front?.dob)?.toString())
        fill(etCountry, bc?.countryOfBirth, front?.countryOfBirth)

        val idInfo = SaId.analyse(etId.text?.toString())
        val sex = bc?.sex ?: front?.sex ?: idInfo.sex
        if (spSex.selectedItemPosition == 0 && sex != null) spSex.setSelection(if (sex == "M") 1 else 2)
        val citizen = idInfo.citizen
        if (spCitizenship.selectedItemPosition == 0 && citizen != null) spCitizenship.setSelection(if (citizen) 1 else 2)
    }

    private fun reset() {
        Session.clear()
        listOf(etNames, etSurname, etId, etDob, etCountry).forEach { it.setText("") }
        listOf(spSex, spCitizenship, spMarital, spCriminal, spQualification).forEach { it.setSelection(0) }
        tvResults.text = "Results will appear here"
        btnInspector.isEnabled = false
        btnExport.isEnabled = false
        refresh()
    }

    private fun openInspector() {
        startActivity(
            Intent(this, InspectorActivity::class.java)
                .putExtra("id", etId.text?.toString()?.trim())
                .putExtra("names", etNames.text?.toString()?.trim())
                .putExtra("surname", etSurname.text?.toString()?.trim())
        )
    }

    private fun exportData() {
        val id = etId.text?.toString()?.trim().orEmpty()
        val names = etNames.text?.toString()?.trim().orEmpty()
        val surname = etSurname.text?.toString()?.trim().orEmpty()
        Toast.makeText(this, "Preparing export...", Toast.LENGTH_SHORT).show()
        worker.execute {
            try {
                val file = Exporter.export(this, id, names, surname)
                val uri = FileProvider.getUriForFile(this, "$packageName.export", file)
                val share = Intent(Intent.ACTION_SEND)
                    .setType("application/zip")
                    .putExtra(Intent.EXTRA_STREAM, uri)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                runOnUiThread { startActivity(Intent.createChooser(share, "Export Horkos data")) }
            } catch (e: Exception) {
                runOnUiThread { Toast.makeText(this, "Export failed: ${e.message}", Toast.LENGTH_LONG).show() }
            }
        }
    }

    // ---------------- Verification ----------------

    private enum class Level { PASS, WARN, FAIL }
    private class Check(val section: String, val level: Level, val label: String, val detail: String)

    private fun f(x: Float?, d: Int = 2): String = if (x == null) "-" else String.format(Locale.ROOT, "%.${d}f", x)
    private fun yn(b: Boolean) = if (b) "YES" else "NO"
    private fun icon(l: Level) = when (l) {
        Level.PASS -> "✅"
        Level.WARN -> "⚠️"
        Level.FAIL -> "❌"
    }

    private fun verify() {
        val names = etNames.text?.toString()?.trim().orEmpty()
        val surname = etSurname.text?.toString()?.trim().orEmpty()
        val id = etId.text?.toString()?.trim().orEmpty()
        val dobField = Dates.parse(etDob.text?.toString())
        val sexField = when (spSex.selectedItemPosition) {
            1 -> "M"
            2 -> "F"
            else -> null
        }
        val citizenship = spCitizenship.selectedItemPosition
        val marital = spMarital.selectedItem?.toString().orEmpty()
        val criminal = spCriminal.selectedItem?.toString().orEmpty()
        val qualification = spQualification.selectedItem?.toString().orEmpty()

        val missing = mutableListOf<String>()
        if (names.isEmpty()) missing.add("first name")
        if (surname.isEmpty()) missing.add("surname")
        if (id.isEmpty()) missing.add("ID number")
        if (dobField == null) missing.add("date of birth")
        if (sexField == null) missing.add("sex")
        if (citizenship == 0) missing.add("citizenship")
        if (spMarital.selectedItemPosition == 0) missing.add("marital status")
        if (spCriminal.selectedItemPosition == 0) missing.add("criminal record")
        if (spQualification.selectedItemPosition == 0) missing.add("highest qualification")

        tvResults.text = "Checking... (running face mesh and models)"
        btnInspector.isEnabled = false
        btnExport.isEnabled = false
        worker.execute {
            val text = try {
                runChecks(names, surname, id, dobField, sexField, citizenship, missing)
            } catch (e: Exception) {
                "Error during checks: $e"
            }
            val full = text + "\n\nMarital status: $marital\nCriminal record: $criminal\nHighest qualification: $qualification"
            Session.report = full
            runOnUiThread {
                tvResults.text = full
                btnInspector.isEnabled = true
                btnExport.isEnabled = true
                refresh()
            }
        }
    }

    private fun runChecks(
        names: String, surname: String, id: String, dobField: LocalDate?, sexField: String?,
        citizenship: Int, missing: List<String>
    ): String {
        val checks = mutableListOf<Check>()
        val doc = "ID document"
        val nameSec = "Name verification"
        val faceSec = "Face & liveness"
        val formSec = "Form"
        fun add(sec: String, lv: Level, label: String, detail: String) {
            checks.add(Check(sec, lv, label, detail))
        }
        val digits = id.filter { it.isDigit() }

        // ---- ID document ----
        add(formSec, if (missing.isEmpty()) Level.PASS else Level.FAIL, "Form complete",
            if (missing.isEmpty()) "All fields filled" else "Missing: ${missing.joinToString()}")

        val info = SaId.analyse(id)
        when {
            !info.formatOk -> add(doc, Level.FAIL, "ID number format", "Must be 13 digits with a valid date")
            !info.checksumOk -> add(doc, Level.FAIL, "ID number checksum", "Luhn check digit is wrong (typo or fake number)")
            else -> add(doc, Level.PASS, "ID number checksum", "Luhn valid (maths in inspector)")
        }
        val idDob = info.dob
        if (idDob != null && dobField != null) {
            add(doc, if (idDob == dobField) Level.PASS else Level.FAIL, "Date of birth vs ID digits 1-6",
                if (idDob == dobField) "Matches $idDob" else "ID says $idDob, form says $dobField")
        }
        val idSex = info.sex
        if (idSex != null && sexField != null) {
            add(doc, if (idSex == sexField) Level.PASS else Level.FAIL, "Sex vs ID digits 7-10",
                "Digits 7-10 " + (if (idSex == "M") ">= 5000" else "< 5000") + " -> $idSex, form says $sexField")
        }
        val idCitizen = info.citizen
        if (idCitizen != null && citizenship != 0) {
            val ok = (idCitizen && citizenship == 1) || (!idCitizen && citizenship == 2)
            add(doc, if (ok) Level.PASS else Level.FAIL, "Citizenship vs ID digit 11",
                "Digit ${digits[10]} -> " + (if (idCitizen) "citizen" else "permanent resident"))
        }
        if (dobField != null && dobField.isAfter(LocalDate.now().minusYears(18))) add(doc, Level.WARN, "Age", "Under 18")

        val front = Session.ocrFront
        if (front == null) {
            add(doc, Level.WARN, "ID front", "Not captured")
        } else {
            val fid = front.idNumber
            if (fid == null) add(doc, Level.WARN, "Printed ID number (front)", "Could not read")
            else add(doc, if (fid == digits) Level.PASS else Level.FAIL, "Printed ID number (front) vs form", fid)
        }

        val bc = Session.barcode
        val c39 = Session.code39?.filter { it.isDigit() }
        if (bc == null) {
            add(doc, Level.FAIL, "Back of ID", "Not scanned - barcodes not checked")
        } else {
            add(doc, if (bc.idNumber == digits) Level.PASS else Level.FAIL, "PDF417 ID number vs form", "${bc.idNumber}")
            if (c39.isNullOrEmpty()) add(doc, Level.WARN, "Code 39 barcode", "Not read")
            else add(doc, if (c39 == bc.idNumber) Level.PASS else Level.FAIL, "Code 39 vs PDF417", "$c39 vs ${bc.idNumber}")
            val bs = bc.surname
            if (bs != null) add(doc, if (Names.matches(bs, surname)) Level.PASS else Level.FAIL, "PDF417 surname vs form", bs)
            val bn = bc.names
            if (bn != null) add(doc, if (Names.matches(bn, names)) Level.PASS else Level.FAIL, "PDF417 names vs form", bn)
            val fs = front?.surname
            if (fs != null && bs != null) {
                add(doc, if (Names.matches(fs, bs)) Level.PASS else Level.WARN, "Printed surname vs PDF417", "OCR read '$fs'")
            }
        }

        val backCard = Session.ocrBack?.cardNumber
        val bcCard = bc?.cardNumber
        when {
            backCard != null && bcCard != null -> add(doc, if (backCard == bcCard) Level.PASS else Level.FAIL,
                "Card number: printed vs barcode", "$backCard vs $bcCard")
            backCard != null -> add(doc, Level.WARN, "Card number", "Printed $backCard (not in barcode, so not cross-checked)")
            bcCard != null -> add(doc, Level.WARN, "Card number", "Barcode has $bcCard but the printed one was not read")
            else -> add(doc, Level.WARN, "Card number", "Not found")
        }

        val printedIssue = Session.ocrBack?.issueDate ?: front?.issueDate
        val bcIssue = bc?.issueDate
        val issue = bcIssue ?: printedIssue
        if (issue == null) {
            add(doc, Level.WARN, "Date of issue", "Not found on the card or barcode")
        } else {
            val problems = mutableListOf<String>()
            if (issue.isAfter(LocalDate.now())) problems.add("in the future")
            if (issue.isBefore(LocalDate.of(2013, 7, 18))) problems.add("before Smart ID cards existed (18 Jul 2013)")
            val dob = idDob ?: dobField
            if (dob != null && issue.isBefore(dob.plusYears(16))) problems.add("before the holder turned 16")
            if (printedIssue != null && bcIssue != null && printedIssue != bcIssue) problems.add("printed $printedIssue vs barcode $bcIssue")
            add(doc, if (problems.isEmpty()) Level.PASS else Level.FAIL, "Date of issue",
                if (problems.isEmpty()) "$issue looks valid" else "$issue: ${problems.joinToString()}")
        }

        // ---- Name verification ----
        val st = Session.statement
        if (st == null) {
            add(nameSec, Level.WARN, "Proof of account", "Not uploaded - name and surname are only CONSISTENT with the ID, not independently verified")
        } else if (st.error != null) {
            add(nameSec, Level.FAIL, "Proof of account", "Could not read: ${st.error}")
        } else {
            val (ok, detail) = StatementCheck.nameMatch(st.text, names, surname)
            add(nameSec, if (ok) Level.PASS else Level.FAIL, "Name on proof of account",
                (if (ok) "Confirmed by ${st.bank ?: "statement"}: " else "Not matched: ") + detail)
            val flags = st.redFlags()
            if (flags.isEmpty()) add(nameSec, Level.PASS, "Statement integrity", "No tampering signs found (details in inspector)")
            else flags.forEach { add(nameSec, Level.WARN, "Statement integrity", it) }
            if (st.signatures.isNotEmpty() && st.signatureCoversFile == true) {
                add(nameSec, Level.PASS, "Statement digital signature", "Present and unchanged since signing (signer not validated)")
            }
        }

        // ---- Face & liveness ----
        val lv = Session.liveness
        if (lv == null) add(faceSec, Level.FAIL, "Face scan", "Not done")
        else add(faceSec, if (lv.completed) Level.PASS else Level.FAIL, "Liveness challenges",
            "${lv.steps.size} completed: ${lv.steps.joinToString()}" + (if (lv.completed) "" else " - ${lv.message}"))

        val frontal = setOf("CENTER", "FINAL", "BLINK", "CLOSER", "FARTHER")
        val cardFace = Session.cardFace
        try {
            val models = FaceModels.get(this)
            if (cardFace != null) {
                Session.cardFaceMesh = try { FaceAnalysis.mesh(cardFace) } catch (e: Exception) { null }
                Session.cardAligned = FaceAnalysis.align(cardFace, Session.cardFaceMesh)
                Session.cardEmbedding = models.embedding(Session.cardAligned ?: cardFace)
            }
            val cardEmb = Session.cardEmbedding
            for (k in Session.keyframes) {
                k.mesh = try { FaceAnalysis.mesh(k.frame) } catch (e: Exception) { null }
                k.parallax = FaceAnalysis.parallax(k.mesh)
                val crop = ImageUtils.cropFace(k.frame, k.box)
                k.aligned = FaceAnalysis.align(k.frame, k.mesh)
                val emb = models.embedding(k.aligned ?: crop)
                k.embedding = emb
                if (cardEmb != null) k.similarity = FaceModels.cosine(cardEmb, emb)
                if (k.label in frontal) k.spoof = models.spoofScore(crop)
            }
        } catch (e: Exception) {
            add(faceSec, Level.FAIL, "Face models", "Error: ${e.message}")
        }

        fun px(label: String): Float? = Session.keyframes.filter { it.label == label }.mapNotNull { it.parallax }.firstOrNull()
        val centres = listOfNotNull(px("CENTER"), px("FINAL"))
        val pc = if (centres.isEmpty()) null else centres.average().toFloat()
        val pl = px("LEFT")
        val pr = px("RIGHT")
        if (pc != null && pl != null && pr != null) {
            val dl = pl - pc
            val dr = pr - pc
            val ok = abs(dl) > 0.06f && abs(dr) > 0.06f && dl * dr < 0f
            add(faceSec, if (ok) Level.PASS else Level.FAIL, "3D parallax (nose vs cheeks)",
                "centre ${f(pc, 3)}, left ${f(pl, 3)} (shift ${f(dl, 3)}), right ${f(pr, 3)} (shift ${f(dr, 3)}); a flat photo stays near 0")
        } else {
            add(faceSec, Level.WARN, "3D parallax", "Face mesh not available for centre/left/right poses")
        }

        val base = Session.flashes.firstOrNull { it.color == "BASELINE" }
        if (base == null || Session.flashes.size < 4) {
            add(faceSec, Level.WARN, "Screen-flash reflection", "Not enough flash frames captured (${Session.flashes.size})")
        } else {
            val b0 = FaceAnalysis.chroma(base.rgb)
            val g0 = FaceAnalysis.chroma(base.bg)
            val parts = mutableListOf<String>()
            var hits = 0
            for ((name, ch) in listOf("RED" to 0, "GREEN" to 1, "BLUE" to 2)) {
                val s = Session.flashes.firstOrNull { it.color == name } ?: continue
                val faceShift = FaceAnalysis.chroma(s.rgb)[ch] - b0[ch]
                val rel = faceShift - (FaceAnalysis.chroma(s.bg)[ch] - g0[ch])
                if (rel > 0.01f || faceShift > 0.02f) hits++
                parts.add(name + " face " + f(faceShift, 3) + " rel " + f(rel, 3))
            }
            val white = Session.flashes.firstOrNull { it.color == "WHITE" }
            val gain = if (white == null) null else FaceAnalysis.luminance(white.rgb) / (FaceAnalysis.luminance(base.rgb) + 0.001f)
            add(faceSec, if (hits >= 2) Level.PASS else Level.FAIL, "Screen-flash reflection",
                "$hits/3 colours reflected (" + parts.joinToString() + "), white flash brightness x" + f(gain))
        }

        val spoofs = Session.keyframes.filter { it.label == "CENTER" || it.label == "FINAL" }.mapNotNull { it.spoof }
        if (spoofs.isNotEmpty()) {
            val m = spoofs.average().toFloat()
            add(faceSec, if (m < FaceModels.SPOOF_THRESHOLD) Level.PASS else Level.FAIL, "Anti-spoof model",
                "mean score ${f(m, 3)} (real if below ${FaceModels.SPOOF_THRESHOLD})")
        }

        val sims = Session.keyframes.filter { it.label in frontal }.mapNotNull { it.similarity }
        if (cardFace == null) {
            add(faceSec, Level.FAIL, "Face match", "No ID photo captured")
        } else if (sims.isEmpty()) {
            add(faceSec, Level.FAIL, "Face match", "No live frames to compare")
        } else {
            val best = sims.max()
            val mean = sims.average().toFloat()
            add(faceSec, if (best >= FaceModels.MATCH_THRESHOLD) Level.PASS else Level.FAIL, "Face match vs ID photo",
                "best ${f(best)}, mean ${f(mean)} over ${sims.size} frames (pass at ${FaceModels.MATCH_THRESHOLD}), eye-aligned ID photo: " + yn(Session.cardAligned != null))
        }

        val embs = Session.keyframes.filter { it.label in frontal }.mapNotNull { it.embedding }
        if (embs.size >= 2) {
            var minS = 1f
            for (i in embs.indices) for (j in i + 1 until embs.size) minS = minOf(minS, FaceModels.cosine(embs[i], embs[j]))
            add(faceSec, if (minS >= 0.6f) Level.PASS else Level.FAIL, "Same person throughout scan",
                "lowest similarity between live frames ${f(minS)}")
        }
        add(faceSec, Level.WARN, "Home Affairs", "Not checked (offline test version)")

        // ---- Report ----
        val fails = checks.count { it.level == Level.FAIL }
        val warns = checks.count { it.level == Level.WARN }
        fun sectionOk(s: String) = checks.none { it.section == s && it.level == Level.FAIL }
        val nameVerified = checks.any { it.label == "Name on proof of account" && it.level == Level.PASS }
        return buildString {
            appendLine(if (fails == 0) "✅ PASSED LOCAL CHECKS ($warns warnings)" else "❌ NOT VERIFIED ($fails failed, $warns warnings)")
            appendLine("Form complete: ${yn(sectionOk(formSec))}")
            appendLine("ID document consistent: ${yn(sectionOk(doc))}")
            appendLine("Name verified by bank statement: ${yn(nameVerified)}")
            appendLine("Live person matches ID photo: ${yn(sectionOk(faceSec) && lv != null)}")
            for (sec in listOf(formSec, doc, nameSec, faceSec)) {
                appendLine()
                appendLine("--- $sec ---")
                checks.filter { it.section == sec }.forEach { appendLine("${icon(it.level)} ${it.label}: ${it.detail}") }
            }
        }.trim()
    }
}
