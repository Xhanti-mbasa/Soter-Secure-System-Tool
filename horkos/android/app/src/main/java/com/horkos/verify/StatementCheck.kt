package com.horkos.verify

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.pdf.PdfRenderer
import android.net.Uri
import android.os.ParcelFileDescriptor
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import java.io.File
import java.time.LocalDate

class StatementResult(
    val fileName: String,
    val sizeBytes: Int,
    val pages: Int,
    val encrypted: Boolean,
    val unlockedWith: String?,
    val textSource: String,
    val text: String,
    val producer: String?,
    val creator: String?,
    val created: String?,
    val modified: String?,
    val eofCount: Int,
    val signatures: List<String>,
    val signatureCoversFile: Boolean?,
    val bank: String?,
    val statementDate: LocalDate?,
    val error: String?
) {
    fun summary(): String = buildString {
        appendLine("File: $fileName (${sizeBytes / 1024} KB, $pages pages)")
        appendLine("Encrypted: $encrypted" + (unlockedWith?.let { " (opened with $it)" } ?: ""))
        appendLine("Text source: $textSource")
        appendLine("Producer: ${producer ?: "-"}")
        appendLine("Creator: ${creator ?: "-"}")
        appendLine("Created: ${created ?: "-"}")
        appendLine("Modified: ${modified ?: "-"}")
        appendLine("%%EOF markers (save revisions): $eofCount")
        appendLine("Digital signatures: " + (if (signatures.isEmpty()) "none" else signatures.joinToString("; ")))
        appendLine("Signature covers whole file: ${signatureCoversFile ?: "n/a"}")
        appendLine("Bank detected: ${bank ?: "none"}")
        appendLine("Statement date (latest date in text): ${statementDate ?: "-"}")
    }.trim()

    fun redFlags(): List<String> {
        val f = mutableListOf<String>()
        val tools = ((producer ?: "") + " " + (creator ?: "")).uppercase()
        StatementCheck.editors.firstOrNull { tools.contains(it) }?.let { f.add("Made or edited with $it") }
        if (created != null && modified != null && created != modified) f.add("Modified after creation ($created -> $modified)")
        if (eofCount > 1 && signatures.isEmpty()) f.add("$eofCount save revisions (incremental edits) and no digital signature")
        if (signatureCoversFile == false) f.add("File was changed after it was signed")
        if (bank == null) f.add("No known SA bank name found in the text")
        val d = statementDate
        if (d != null && d.isBefore(LocalDate.now().minusMonths(3))) f.add("Statement older than 3 months ($d)")
        if (text.isBlank()) f.add("No readable text")
        return f
    }
}

object StatementCheck {
    private val banks = listOf(
        "CAPITEC", "FIRST NATIONAL BANK", "FNB", "ABSA", "STANDARD BANK", "NEDBANK", "DISCOVERY BANK",
        "TYMEBANK", "TYME BANK", "AFRICAN BANK", "INVESTEC", "BIDVEST BANK", "OLD MUTUAL", "SASFIN", "BANK ZERO"
    )
    val editors = listOf(
        "PHOTOSHOP", "ILLUSTRATOR", "MICROSOFT WORD", "CANVA", "ILOVEPDF", "SMALLPDF", "SEJDA", "PDFESCAPE",
        "PDF-XCHANGE", "LIBREOFFICE", "OPENOFFICE", "GOOGLE DOCS", "INKSCAPE", "GIMP", "PDFFILLER", "DOCHUB"
    )

    fun fail(name: String, error: String) = StatementResult(
        name, 0, 0, false, null, "-", "", null, null, null, null, 0, emptyList(), null, null, null, error
    )

    /** Opens the PDF (trying the ID number as password), extracts text and forensic metadata. Off main thread. */
    fun analyse(context: Context, uri: Uri, idNumber: String?): StatementResult {
        val name = uri.lastPathSegment ?: "statement.pdf"
        val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
            ?: return fail(name, "Could not read the file")
        PDFBoxResourceLoader.init(context.applicationContext)
        val eof = Regex("%%EOF").findAll(String(bytes, Charsets.ISO_8859_1)).count()

        val id = idNumber.orEmpty()
        val passwords = listOf("" to "no password", id to "ID number", id.takeLast(6) to "last 6 of ID", id.take(6) to "first 6 of ID")
            .filter { it.first.isNotEmpty() || it.second == "no password" }
        var doc: PDDocument? = null
        var unlockedWith: String? = null
        var lastError: String? = null
        for ((pw, label) in passwords) {
            try {
                doc = PDDocument.load(bytes, pw)
                unlockedWith = if (pw.isEmpty()) null else label
                break
            } catch (e: Exception) {
                lastError = e.javaClass.simpleName + ": " + (e.message ?: "")
            }
        }
        val d = doc ?: return fail(name, "Could not open PDF (password protected?) - $lastError")

        try {
            val encrypted = d.isEncrypted
            if (encrypted) d.isAllSecurityToBeRemoved = true
            val info = d.documentInformation
            val sigDicts = d.signatureDictionaries
            val sigs = sigDicts.map { s ->
                "${s.name ?: "unnamed"} (${s.filter ?: "?"} / ${s.subFilter ?: "?"}) signed ${s.signDate?.time ?: "?"}"
            }
            val covers = sigDicts.lastOrNull()?.byteRange?.let { br -> br.size == 4 && br[2] + br[3] == bytes.size }
            val stripper = PDFTextStripper()
            stripper.startPage = 1
            stripper.endPage = minOf(3, d.numberOfPages)
            var text = stripper.getText(d)
            var source = "embedded PDF text"
            if (text.isBlank() && !encrypted) {
                text = ocr(context, bytes)
                source = "OCR of rendered pages"
            }
            val upper = text.uppercase()
            val today = LocalDate.now()
            return StatementResult(
                fileName = name,
                sizeBytes = bytes.size,
                pages = d.numberOfPages,
                encrypted = encrypted,
                unlockedWith = unlockedWith,
                textSource = source,
                text = text,
                producer = info?.producer,
                creator = info?.creator,
                created = info?.creationDate?.time?.toString(),
                modified = info?.modificationDate?.time?.toString(),
                eofCount = eof,
                signatures = sigs,
                signatureCoversFile = covers,
                bank = banks.firstOrNull { upper.contains(it) },
                statementDate = Dates.findAll(text).filter { !it.isAfter(today) }.maxOrNull(),
                error = null
            )
        } finally {
            d.close()
        }
    }

    private fun ocr(context: Context, bytes: ByteArray): String {
        val f = File(context.cacheDir, "statement_tmp.pdf")
        f.writeBytes(bytes)
        val sb = StringBuilder()
        val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY).use { pfd ->
            val renderer = PdfRenderer(pfd)
            try {
                for (i in 0 until minOf(2, renderer.pageCount)) {
                    val page = renderer.openPage(i)
                    try {
                        val bmp = Bitmap.createBitmap(page.width * 2, page.height * 2, Bitmap.Config.ARGB_8888)
                        bmp.eraseColor(Color.WHITE)
                        page.render(bmp, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                        sb.appendLine(Tasks.await(recognizer.process(InputImage.fromBitmap(bmp, 0))).text)
                    } finally {
                        page.close()
                    }
                }
            } finally {
                renderer.close()
            }
        }
        f.delete()
        return sb.toString()
    }

    /** Surname must appear, plus a first name or matching initials (e.g. "MR X L DAKA"). */
    fun nameMatch(text: String, names: String, surname: String): Pair<Boolean, String> {
        val t = " " + Names.normalise(text) + " "
        val sTokens = Names.normalise(surname).split(" ").filter { it.isNotEmpty() }
        val fTokens = Names.normalise(names).split(" ").filter { it.isNotEmpty() }
        if (sTokens.isEmpty() || fTokens.isEmpty()) return false to "Fill in first name and surname first"
        val surnameOk = sTokens.all { t.contains(" $it ") }
        val firstFound = fTokens.filter { t.contains(" $it ") }
        val initialRegex = Regex("((?:[A-Z] ){1,4})" + Regex.escape(sTokens.joinToString(" ")) + " ")
        val initials = initialRegex.findAll(t).map { it.groupValues[1].replace(" ", "") }.toList()
        val initialsOk = initials.any { it.isNotEmpty() && it[0] == fTokens[0][0] }
        val ok = surnameOk && (firstFound.isNotEmpty() || initialsOk)
        val detail = "surname " + (if (surnameOk) "found" else "NOT found") +
            "; first names found: " + (if (firstFound.isEmpty()) "none" else firstFound.joinToString()) +
            "; initials before surname: " + (if (initials.isEmpty()) "none" else initials.joinToString())
        return ok to detail
    }
}
