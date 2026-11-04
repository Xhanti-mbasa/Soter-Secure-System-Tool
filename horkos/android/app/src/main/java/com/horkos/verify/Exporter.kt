package com.horkos.verify

import android.content.Context
import android.graphics.Bitmap
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * Zips every check, score, mesh, embedding and face image for analysis - with the ID number removed.
 * ID card photos are left out because the ID number is printed on them.
 */
object Exporter {
    private fun f(x: Float?, d: Int = 3): String = if (x == null) "" else String.format(Locale.ROOT, "%.${d}f", x)

    fun redact(text: String?, id: String): String {
        var t = text ?: ""
        val digits = id.filter { it.isDigit() }
        if (digits.length >= 6) t = t.replace(digits, "[ID REMOVED]")
        t = t.replace(Regex("(?<![0-9])[0-9]{6} ?[0-9]{4} ?[0-9] ?[0-9] ?[0-9](?![0-9])"), "[ID REMOVED]")
        return t
    }

    private fun meshCsv(m: List<FloatArray>): String = buildString {
        appendLine("index,x,y,z")
        m.forEachIndexed { i, p -> appendLine("$i," + f(p[0], 2) + "," + f(p[1], 2) + "," + f(p[2], 2)) }
    }

    fun export(context: Context, id: String, names: String, surname: String): File {
        val dir = File(context.cacheDir, "export")
        dir.deleteRecursively()
        dir.mkdirs()
        val stamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.ROOT).format(Date())
        val out = File(dir, "horkos-export-$stamp.zip")
        ZipOutputStream(FileOutputStream(out)).use { zip ->
            fun text(name: String, body: String) {
                zip.putNextEntry(ZipEntry(name))
                zip.write(redact(body, id).toByteArray())
                zip.closeEntry()
            }
            fun png(name: String, b: Bitmap?) {
                if (b == null) return
                val bos = ByteArrayOutputStream()
                b.compress(Bitmap.CompressFormat.PNG, 100, bos)
                zip.putNextEntry(ZipEntry(name))
                zip.write(bos.toByteArray())
                zip.closeEntry()
            }

            text("README.txt", "Horkos export $stamp. The ID number has been removed from every file. ID card photos are not included because they show the ID number.")
            text("01_verification_report.txt", Session.report ?: "Verify was not run.")
            text("02_id_number_checks.txt", SaId.explainRedacted(id))

            val bc = Session.barcode
            text("03_barcodes.txt", buildString {
                appendLine("Code 39 read: " + (if (Session.code39 != null) "yes" else "no"))
                if (bc == null) {
                    appendLine("PDF417 not read")
                } else {
                    appendLine("PDF417 fields:")
                    bc.raw.split('|').forEachIndexed { i, v -> appendLine("[$i] $v") }
                    appendLine()
                    appendLine(bc.summary())
                }
            })
            text("04_ocr_front.txt", buildString {
                appendLine(Session.ocrFront?.summary() ?: "not captured")
                appendLine()
                appendLine("Raw OCR:")
                appendLine(Session.ocrFront?.raw ?: "")
            })
            text("05_ocr_back.txt", buildString {
                appendLine(Session.ocrBack?.summary() ?: "not captured")
                appendLine()
                appendLine("Raw OCR:")
                appendLine(Session.ocrBack?.raw ?: "")
            })

            val st = Session.statement
            text("06_proof_of_account.txt", if (st == null) "Not uploaded" else buildString {
                appendLine(st.summary())
                st.error?.let { appendLine("Error: $it") }
                val (ok, detail) = StatementCheck.nameMatch(st.text, names, surname)
                appendLine("Name match: " + (if (ok) "YES" else "NO") + " - " + detail)
                appendLine("Red flags: " + st.redFlags().joinToString("; ").ifEmpty { "none" })
                appendLine()
                appendLine("Extracted text (first 3000 chars):")
                appendLine(st.text.take(3000))
            })

            val lv = Session.liveness
            text("07_face_scan.csv", buildString {
                appendLine("# result: " + (lv?.message ?: "not done") + "; steps: " + (lv?.steps?.joinToString(" > ") ?: ""))
                appendLine("index,label,time_ms,yaw,pitch,roll,left_eye_open,right_eye_open,face_width_ratio,mesh_points,nose_parallax,nose_depth,similarity_to_id,spoof_score,eye_aligned")
                Session.keyframes.forEachIndexed { i, k ->
                    appendLine(
                        listOf(
                            i, k.label, k.timeMs, f(k.yaw, 1), f(k.pitch, 1), f(k.roll, 1), f(k.leftEye), f(k.rightEye),
                            f(k.sizeRatio), k.mesh?.size ?: 0, f(k.parallax), f(FaceAnalysis.noseDepth(k.mesh), 2),
                            f(k.similarity), f(k.spoof), k.aligned != null
                        ).joinToString(",")
                    )
                }
            })
            text("08_embeddings_192d.csv", buildString {
                Session.cardEmbedding?.let { e -> appendLine("ID_PHOTO," + e.joinToString(",") { v -> f(v, 5) }) }
                Session.keyframes.forEachIndexed { i, k ->
                    k.embedding?.let { e -> appendLine("${i}_${k.label}," + e.joinToString(",") { v -> f(v, 5) }) }
                }
            })
            text("09_flash_test.csv", buildString {
                appendLine("color,face_r,face_g,face_b,background_r,background_g,background_b,face_share_r,face_share_g,face_share_b")
                for (s in Session.flashes) {
                    val c = FaceAnalysis.chroma(s.rgb)
                    appendLine(
                        listOf(
                            s.color, f(s.rgb[0], 1), f(s.rgb[1], 1), f(s.rgb[2], 1),
                            f(s.bg[0], 1), f(s.bg[1], 1), f(s.bg[2], 1), f(c[0]), f(c[1]), f(c[2])
                        ).joinToString(",")
                    )
                }
            })
            Session.cardFaceMesh?.let { m -> text("mesh/id_photo_mesh.csv", meshCsv(m)) }
            Session.keyframes.forEachIndexed { i, k -> k.mesh?.let { m -> text("mesh/${i}_${k.label}_mesh.csv", meshCsv(m)) } }

            val cf = Session.cardFace
            if (cf != null) {
                png("images/id_photo_face_mesh.png", FaceAnalysis.drawMesh(cf, Session.cardFaceMesh, null))
                png("images/id_photo_aligned_112.png", Session.cardAligned)
            }
            Session.keyframes.forEachIndexed { i, k ->
                png("images/${i}_${k.label}_mesh.png", FaceAnalysis.drawMesh(k.frame, k.mesh, k.box))
                png("images/${i}_${k.label}_aligned_112.png", k.aligned)
            }
            Session.flashes.forEach { s -> png("images/flash_${s.color}.png", ImageUtils.cropFace(s.frame, s.box, 0.2f)) }
        }
        return out
    }
}
