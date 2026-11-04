# Horkos

*Horkos - Greek god of oaths, who punished anyone who swore falsely.*

Android test app for low-cost South African ID verification. Separate from Soter and Sothis.
Everything runs on the phone; nothing is uploaded or stored. No Home Affairs check yet.

## Flow
1. **ID front** - photo, OCR of printed details, ID photo crop.
2. **ID back** - reads BOTH barcodes (PDF417 + Code 39), OCRs the printed card number and date of issue.
3. **Proof of account** - bank statement PDF: text (or OCR), name/initials match, bank detection, and forensics (producer/creator, created vs modified, save revisions, digital signature coverage). Tries the ID number as the PDF password.
4. **Live face scan** - oval guide, max screen brightness, randomised left/right/up/down, closer/further, blink, then white/red/green/blue screen flashes. A keyframe is kept for every step.
5. **Details form** - names, surname, ID number, DOB, country of birth, sex, citizenship, marital status, criminal record, highest qualification.
6. **Verify** - grouped checks (ID document / name verification / face & liveness) and an **Inspector** with all raw data.

## Checks
- ID number: Luhn checksum, DOB (digits 1-6), sex (7-10, <5000 = F), citizenship (11).
- Printed ID vs PDF417 vs Code 39 vs form; barcode names vs form; printed vs barcode surname.
- Card number printed vs barcode; date of issue (not future, after 18 Jul 2013, holder 16+, printed vs barcode).
- Name is only marked VERIFIED when it matches the proof of account; otherwise it is only consistent with the ID.
- Face: 468-point ML Kit face mesh per keyframe; 3D parallax (nose shift vs cheeks when turning - flat photos stay ~0); screen-flash colour reflection; anti-spoof model; MobileFaceNet cosine similarity vs ID photo; same-person consistency across frames.

## Inspector
Shows the Luhn table, raw barcode fields, raw OCR text, card images, statement metadata and extracted text, every keyframe with the face mesh drawn on it plus angles/eye scores/parallax/similarity/spoof/embedding values, and the flash frames with their colour measurements.

## Stack
Kotlin, CameraX, ML Kit (barcode, text, face detection, face mesh), TensorFlow Lite, PdfBox-Android.
Face models: [Android-MobileFaceNet-MTCNN-FaceAntiSpoofing](https://github.com/syaringan357/Android-MobileFaceNet-MTCNN-FaceAntiSpoofing) (MIT), downloaded at build time with pinned checksums.

## Build
`.github/workflows/horkos-apk-build.yml` builds on every push to `horkos/` and publishes a pre-release tagged `horkos-v0.2.N`.

## Known limits (test version)
- Barcodes are unsigned plain text - they prove consistency, not authenticity.
- Thresholds (face match 0.55, spoof 0.2, parallax 0.06, flash 0.01) are untuned.
- Without a `HORKOS_KEYSTORE_B64` secret each build uses a new throwaway key: uninstall before installing a new build.
- ID data, face images and criminal record are special personal information under POPIA - get consent before testing on real people.
