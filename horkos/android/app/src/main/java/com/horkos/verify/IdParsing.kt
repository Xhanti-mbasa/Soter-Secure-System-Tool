package com.horkos.verify

import com.google.mlkit.vision.text.Text
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeFormatterBuilder
import java.util.Locale

/** Details read from an ID (barcode or OCR). Any field can be null if not found. */
data class IdDetails(
    val source: String,
    val surname: String? = null,
    val names: String? = null,
    val sex: String? = null,            // "M" / "F"
    val nationality: String? = null,
    val idNumber: String? = null,
    val dob: LocalDate? = null,
    val countryOfBirth: String? = null,
    val status: String? = null,
    val issueDate: LocalDate? = null,
    val raw: String = ""
) {
    fun summary(): String = buildString {
        appendLine("Source: $source")
        surname?.let { appendLine("Surname: $it") }
        names?.let { appendLine("Names: $it") }
        idNumber?.let { appendLine("ID number: $it") }
        dob?.let { appendLine("Date of birth: $it") }
        sex?.let { appendLine("Sex: $it") }
        nationality?.let { appendLine("Nationality: $it") }
        countryOfBirth?.let { appendLine("Country of birth: $it") }
        status?.let { appendLine("Status: $it") }
        issueDate?.let { appendLine("Date of issue: $it") }
    }.trim()
}

/** Facts encoded in a South African ID number (YYMMDD SSSS C A Z). */
data class SaIdInfo(
    val formatOk: Boolean,
    val checksumOk: Boolean,
    val dob: LocalDate?,
    val sex: String?,          // "M" / "F"
    val citizen: Boolean?      // true = SA citizen, false = permanent resident
)

object SaId {
    fun analyse(id: String?): SaIdInfo {
        val clean = id?.filter { it.isDigit() } ?: ""
        if (clean.length != 13) return SaIdInfo(false, false, null, null, null)
        val yy = clean.substring(0, 2).toInt()
        val mm = clean.substring(2, 4).toInt()
        val dd = clean.substring(4, 6).toInt()
        val currentYy = LocalDate.now().year % 100
        val year = if (yy > currentYy) 1900 + yy else 2000 + yy
        val dob = runCatching { LocalDate.of(year, mm, dd) }.getOrNull()
        val gender = clean.substring(6, 10).toInt()
        val sex = if (gender < 5000) "F" else "M"
        val citizen = when (clean[10]) {
            '0' -> true
            '1' -> false
            else -> null
        }
        return SaIdInfo(dob != null, luhn(clean), dob, sex, citizen)
    }

    fun luhn(digits: String): Boolean {
        var sum = 0
        var alt = false
        for (i in digits.indices.reversed()) {
            var n = digits[i] - '0'
            if (alt) {
                n *= 2
                if (n > 9) n -= 9
            }
            sum += n
            alt = !alt
        }
        return sum % 10 == 0
    }
}

object Dates {
    private val formatters: List<DateTimeFormatter> = listOf(
        "dd MMM yyyy", "d MMM yyyy", "dd MMMM yyyy", "yyyy-MM-dd", "dd/MM/yyyy",
        "dd-MM-yyyy", "yyyy/MM/dd", "dd.MM.yyyy", "yyyyMMdd", "dd-MMM-yyyy"
    ).map {
        DateTimeFormatterBuilder().parseCaseInsensitive().appendPattern(it).toFormatter(Locale.ENGLISH)
    }

    fun parse(text: String?): LocalDate? {
        if (text.isNullOrBlank()) return null
        val t = text.trim().replace(Regex("\\s+"), " ")
        for (f in formatters) {
            val d = runCatching { LocalDate.parse(t, f) }.getOrNull()
            if (d != null && d.year in 1900..2100) return d
        }
        return null
    }

    /** Finds the first date-looking substring inside free text. */
    fun find(text: String): LocalDate? {
        val patterns = listOf(
            Regex("\\b\\d{1,2} [A-Za-z]{3,9} \\d{4}\\b"),
            Regex("\\b\\d{4}[-/]\\d{2}[-/]\\d{2}\\b"),
            Regex("\\b\\d{2}[-/.]\\d{2}[-/.]\\d{4}\\b")
        )
        for (p in patterns) {
            p.findAll(text).forEach { m -> parse(m.value)?.let { return it } }
        }
        return null
    }
}

object BarcodeParser {
    private val idRegex = Regex("^\\d{13}$")

    fun parse(raw: String): IdDetails {
        val trimmed = raw.trim()
        // Green ID book / Code 39: only the ID number
        if (idRegex.matches(trimmed)) {
            return IdDetails(source = "Barcode (ID number only)", idNumber = trimmed, raw = raw)
        }
        val fields = trimmed.split('|').map { it.trim() }
        if (fields.size < 3) {
            val id = Regex("\\d{13}").find(trimmed)?.value
            return IdDetails(source = "Barcode (unrecognised layout)", idNumber = id, raw = raw)
        }

        val idIdx = fields.indexOfFirst { idRegex.matches(it) }
        val sexIdx = fields.indexOfFirst { it.equals("M", true) || it.equals("F", true) ||
                it.equals("MALE", true) || it.equals("FEMALE", true) }
        val dateIdxs = fields.indices.filter { Dates.parse(fields[it]) != null }
        val dobIdx = dateIdxs.firstOrNull { it > idIdx } ?: dateIdxs.firstOrNull()
        val issueIdx = dateIdxs.firstOrNull { dobIdx != null && it > dobIdx }

        fun at(i: Int?): String? = i?.let { fields.getOrNull(it) }?.takeIf { it.isNotBlank() }

        val sex = at(sexIdx.takeIf { it >= 0 })?.let { if (it.startsWith("M", true)) "M" else "F" }
        return IdDetails(
            source = "Barcode (PDF417)",
            surname = at(0),
            names = at(1),
            sex = sex,
            nationality = if (sexIdx >= 0) at(sexIdx + 1)?.takeIf { it != at(idIdx) } else null,
            idNumber = at(idIdx.takeIf { it >= 0 }),
            dob = dobIdx?.let { Dates.parse(fields[it]) },
            countryOfBirth = dobIdx?.let { at(it + 1) }?.takeIf { Dates.parse(it) == null },
            status = dobIdx?.let { at(it + 2) }?.takeIf { Dates.parse(it) == null },
            issueDate = issueIdx?.let { Dates.parse(fields[it]) },
            raw = raw
        )
    }
}

/** Reads the printed labels on the front of a South African Smart ID card. */
object OcrParser {
    private val labels = linkedMapOf(
        "country of birth" to "cob",
        "date of birth" to "dob",
        "date of issue" to "issue",
        "identity number" to "id",
        "identity no" to "id",
        "nationality" to "nat",
        "surname" to "surname",
        "names" to "names",
        "status" to "status",
        "sex" to "sex"
    )

    private fun labelOf(line: String): Pair<String, String>? {
        val l = line.lowercase(Locale.ROOT).trim()
        for ((label, key) in labels) {
            if (l.startsWith(label)) return label to key
        }
        return null
    }

    fun parse(text: Text): IdDetails {
        val lines = text.textBlocks.flatMap { b -> b.lines.map { it.text.trim() } }.filter { it.isNotBlank() }
        val values = mutableMapOf<String, String>()
        for (i in lines.indices) {
            val (label, key) = labelOf(lines[i]) ?: continue
            if (values.containsKey(key)) continue
            val inline = lines[i].substring(label.length).trim().trimStart(':').trim()
            val value = when {
                inline.isNotEmpty() -> inline
                i + 1 < lines.size && labelOf(lines[i + 1]) == null -> lines[i + 1]
                else -> null
            }
            if (!value.isNullOrBlank()) values[key] = value
        }

        val allText = text.text
        val id = Regex("\\b\\d{13}\\b").find(allText.replace(" ", ""))?.value
            ?: values["id"]?.filter { it.isDigit() }?.takeIf { it.length == 13 }

        val sex = values["sex"]?.trim()?.firstOrNull()?.uppercaseChar()?.let {
            if (it == 'M') "M" else if (it == 'F') "F" else null
        }
        return IdDetails(
            source = "OCR (front of card)",
            surname = values["surname"],
            names = values["names"],
            sex = sex,
            nationality = values["nat"],
            idNumber = id,
            dob = Dates.parse(values["dob"]) ?: values["dob"]?.let { Dates.find(it) },
            countryOfBirth = values["cob"],
            status = values["status"],
            issueDate = Dates.parse(values["issue"]),
            raw = allText
        )
    }
}

object Names {
    fun normalise(s: String?): String =
        (s ?: "").uppercase(Locale.ROOT).replace(Regex("[^A-Z ]"), " ").replace(Regex("\\s+"), " ").trim()

    /** True if the two names are the same, ignoring case/punctuation, or one contains the other. */
    fun matches(a: String?, b: String?): Boolean {
        val x = normalise(a)
        val y = normalise(b)
        if (x.isEmpty() || y.isEmpty()) return false
        return x == y || x.contains(y) || y.contains(x)
    }
}
