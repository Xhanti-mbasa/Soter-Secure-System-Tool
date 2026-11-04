package com.horkos.verify

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.ImageView
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import java.time.LocalDate
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var tvBarcode: TextView
    private lateinit var tvOcr: TextView
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

    private val worker = Executors.newSingleThreadExecutor()
    private var pendingMode: String? = null

    private val scanLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        refreshFromSession()
    }

    private val permissionLauncher = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        val mode = pendingMode
        if (granted && mode != null) launchScan(mode)
        else Toast.makeText(this, "Camera permission is needed", Toast.LENGTH_LONG).show()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        tvBarcode = findViewById(R.id.tvBarcode)
        tvOcr = findViewById(R.id.tvOcr)
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

        findViewById<MaterialButton>(R.id.btnScanBarcode).setOnClickListener { startScan(ScanActivity.MODE_BARCODE) }
        findViewById<MaterialButton>(R.id.btnCaptureCard).setOnClickListener { startScan(ScanActivity.MODE_CARD) }
        findViewById<MaterialButton>(R.id.btnSelfie).setOnClickListener {
            Session.blinkPassed = false
            Session.turnPassed = false
            Session.selfieFace = null
            startScan(ScanActivity.MODE_SELFIE)
        }
        findViewById<MaterialButton>(R.id.btnVerify).setOnClickListener { verify() }
        findViewById<MaterialButton>(R.id.btnReset).setOnClickListener { reset() }

        // Warm up the face models in the background
        worker.execute { runCatching { FaceModels.get(this) } }
        refreshFromSession()
    }

    override fun onDestroy() {
        super.onDestroy()
        worker.shutdown()
    }

    private fun startScan(mode: String) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            launchScan(mode)
        } else {
            pendingMode = mode
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    private fun launchScan(mode: String) {
        scanLauncher.launch(Intent(this, ScanActivity::class.java).putExtra(ScanActivity.EXTRA_MODE, mode))
    }

    /** Fills the form from the barcode (preferred) or OCR, without overwriting what the user typed. */
    private fun refreshFromSession() {
        val bc = Session.barcode
        val ocr = Session.ocr
        tvBarcode.text = bc?.summary() ?: "No barcode scanned yet"
        tvOcr.text = ocr?.summary() ?: "No ID photo captured yet"
        imgCardFace.setImageBitmap(Session.cardFace)
        imgSelfie.setImageBitmap(Session.selfieFace)

        fun fill(et: TextInputEditText, vararg values: String?) {
            if (et.text.isNullOrBlank()) values.firstOrNull { !it.isNullOrBlank() }?.let { et.setText(it) }
        }
        fill(etNames, bc?.names, ocr?.names)
        fill(etSurname, bc?.surname, ocr?.surname)
        fill(etId, bc?.idNumber, ocr?.idNumber)
        fill(etDob, (bc?.dob ?: ocr?.dob)?.toString())
        fill(etCountry, bc?.countryOfBirth, ocr?.countryOfBirth)

        val idInfo = SaId.analyse(etId.text?.toString())
        val sex = bc?.sex ?: ocr?.sex ?: idInfo.sex
        if (spSex.selectedItemPosition == 0 && sex != null) spSex.setSelection(if (sex == "M") 1 else 2)

        val citizen = idInfo.citizen
        if (spCitizenship.selectedItemPosition == 0 && citizen != null) {
            spCitizenship.setSelection(if (citizen) 1 else 2)
        }
    }

    private fun reset() {
        Session.clear()
        listOf(etNames, etSurname, etId, etDob, etCountry).forEach { it.setText("") }
        listOf(spSex, spCitizenship, spMarital, spCriminal, spQualification).forEach { it.setSelection(0) }
        tvResults.text = "Results will appear here"
        refreshFromSession()
    }

    // ---------------- Verification ----------------

    private enum class Level { PASS, WARN, FAIL }
    private data class Check(val level: Level, val label: String, val detail: String)

    private fun verify() {
        val names = etNames.text?.toString()?.trim().orEmpty()
        val surname = etSurname.text?.toString()?.trim().orEmpty()
        val id = etId.text?.toString()?.trim().orEmpty()
        val dobField = Dates.parse(etDob.text?.toString())
        val sexField = when (spSex.selectedItemPosition) { 1 -> "M"; 2 -> "F"; else -> null }
        val citizenship = spCitizenship.selectedItemPosition
        val marital = spMarital.selectedItem?.toString().orEmpty()
        val criminal = spCriminal.selectedItem?.toString().orEmpty()
        val qualification = spQualification.selectedItem?.toString().orEmpty()

        val missing = mutableListOf<String>()
        if (names.isEmpty()) missing += "first name"
        if (surname.isEmpty()) missing += "surname"
        if (id.isEmpty()) missing += "ID number"
        if (dobField == null) missing += "date of birth"
        if (sexField == null) missing += "sex"
        if (citizenship == 0) missing += "citizenship"
        if (spMarital.selectedItemPosition == 0) missing += "marital status"
        if (spCriminal.selectedItemPosition == 0) missing += "criminal record"
        if (spQualification.selectedItemPosition == 0) missing += "highest qualification"

        tvResults.text = "Checking..."
        val cardFace = Session.cardFace
        val selfie = Session.selfieFace
        val bc = Session.barcode
        val ocr = Session.ocr
        val blink = Session.blinkPassed
        val turn = Session.turnPassed

        worker.execute {
            val checks = mutableListOf<Check>()

            if (missing.isNotEmpty()) checks.add(Check(Level.FAIL, "Form complete", "Missing: ${missing.joinToString()}"))
            else checks.add(Check(Level.PASS, "Form complete", "All fields filled"))

            // ID number structure
            val info = SaId.analyse(id)
            checks.add(
                when {
                    !info.formatOk -> Check(Level.FAIL, "ID number format", "Must be 13 digits with a valid date")
                    !info.checksumOk -> Check(Level.FAIL, "ID number checksum", "Check digit is wrong (typo or fake number)")
                    else -> Check(Level.PASS, "ID number", "Valid format and checksum")
                }
            )
            val idDob = info.dob
            if (idDob != null && dobField != null) {
                checks.add(
                    if (idDob == dobField) Check(Level.PASS, "Date of birth vs ID", "Matches")
                    else Check(Level.FAIL, "Date of birth vs ID", "ID says $idDob, form says $dobField")
                )
            }
            val idSex = info.sex
            if (idSex != null && sexField != null) {
                checks.add(
                    if (idSex == sexField) Check(Level.PASS, "Sex vs ID", "Matches")
                    else Check(Level.FAIL, "Sex vs ID", "ID number indicates $idSex")
                )
            }
            val idCitizen = info.citizen
            if (idCitizen != null && citizenship != 0) {
                val ok = (idCitizen && citizenship == 1) || (!idCitizen && citizenship == 2)
                checks.add(
                    if (ok) Check(Level.PASS, "Citizenship vs ID", "Matches")
                    else Check(Level.FAIL, "Citizenship vs ID", "ID number indicates " + (if (idCitizen) "citizen" else "permanent resident"))
                )
            }
            if (dobField != null && dobField.isAfter(LocalDate.now().minusYears(18))) {
                checks.add(Check(Level.WARN, "Age", "Under 18"))
            }

            // Barcode vs form
            if (bc == null) {
                checks.add(Check(Level.WARN, "Barcode", "Not scanned"))
            } else {
                checks.add(
                    if (bc.idNumber == id) Check(Level.PASS, "Barcode ID number", "Matches form")
                    else Check(Level.FAIL, "Barcode ID number", "Barcode: ${bc.idNumber}")
                )
                if (bc.surname != null) {
                    checks.add(
                        if (Names.matches(bc.surname, surname)) Check(Level.PASS, "Barcode surname", "Matches form")
                        else Check(Level.FAIL, "Barcode surname", "Barcode: ${bc.surname}")
                    )
                }
                if (bc.names != null) {
                    checks.add(
                        if (Names.matches(bc.names, names)) Check(Level.PASS, "Barcode names", "Matches form")
                        else Check(Level.FAIL, "Barcode names", "Barcode: ${bc.names}")
                    )
                }
            }

            // OCR vs barcode (does the printed card agree with its own barcode?)
            if (ocr != null && bc != null) {
                if (ocr.idNumber != null && bc.idNumber != null) {
                    checks.add(
                        if (ocr.idNumber == bc.idNumber) Check(Level.PASS, "Printed ID vs barcode", "Match")
                        else Check(Level.FAIL, "Printed ID vs barcode", "Card ${ocr.idNumber} vs barcode ${bc.idNumber}")
                    )
                }
                if (ocr.surname != null && bc.surname != null) {
                    checks.add(
                        if (Names.matches(ocr.surname, bc.surname)) Check(Level.PASS, "Printed surname vs barcode", "Match")
                        else Check(Level.WARN, "Printed surname vs barcode", "OCR read '${ocr.surname}'")
                    )
                }
            } else if (ocr == null) {
                checks.add(Check(Level.WARN, "ID front", "Not captured"))
            }

            // Liveness
            checks.add(
                if (blink && turn) Check(Level.PASS, "Liveness challenge", "Blink + head turn done")
                else Check(Level.FAIL, "Liveness challenge", "Not completed")
            )

            // Face models
            try {
                val models = FaceModels.get(this)
                if (selfie != null) {
                    val spoof = models.spoofScore(selfie)
                    checks.add(
                        if (spoof < FaceModels.SPOOF_THRESHOLD) Check(Level.PASS, "Anti-spoof", "Real face (score %.3f)".format(spoof))
                        else Check(Level.FAIL, "Anti-spoof", "Looks like photo/screen (score %.3f)".format(spoof))
                    )
                }
                if (cardFace != null && selfie != null) {
                    val sim = models.similarity(cardFace, selfie)
                    checks.add(
                        if (sim >= FaceModels.MATCH_THRESHOLD) Check(Level.PASS, "Face match", "Similarity %.2f (min %.2f)".format(sim, FaceModels.MATCH_THRESHOLD))
                        else Check(Level.FAIL, "Face match", "Similarity %.2f (min %.2f)".format(sim, FaceModels.MATCH_THRESHOLD))
                    )
                } else {
                    checks.add(Check(Level.FAIL, "Face match", "Need both the ID photo and a live selfie"))
                }
            } catch (e: Exception) {
                checks.add(Check(Level.FAIL, "Face models", "Error: ${e.message}"))
            }

            checks.add(Check(Level.WARN, "Home Affairs", "Not checked (offline test version)"))

            val fails = checks.count { it.level == Level.FAIL }
            val warns = checks.count { it.level == Level.WARN }
            val verdict = if (fails > 0) "❌ NOT VERIFIED - $fails failed, $warns warnings"
            else "✅ PASSED LOCAL CHECKS - $warns warnings"
            val text = buildString {
                appendLine(verdict)
                appendLine()
                for (c in checks) {
                    val icon = when (c.level) {
                        Level.PASS -> "✅"
                        Level.WARN -> "⚠️"
                        Level.FAIL -> "❌"
                    }
                    appendLine("$icon ${c.label}: ${c.detail}")
                }
                appendLine()
                appendLine("Marital status: $marital")
                appendLine("Criminal record: $criminal")
                appendLine("Highest qualification: $qualification")
            }
            runOnUiThread { tvResults.text = text }
        }
    }
}
