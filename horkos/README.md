# Horkos

*Horkos - Greek god of oaths, who punished anyone who swore falsely.*

Simple Android test app for low-cost South African ID verification. Separate from Soter and Sothis.

## What it does
1. **Scan ID barcode** - reads the PDF417 on the back of the Smart ID (or Code 39 on a green ID book) with ML Kit and pre-fills the form.
2. **Capture ID front** - photographs the card, OCRs the printed details and crops the ID photo.
3. **Live selfie** - front camera; user must blink, turn their head, then look straight. The face is cropped from that frame.
4. **Details form** - names, surname, ID number, DOB, country of birth, sex, citizenship, marital status, criminal record, highest qualification.
5. **Verify** - checklist: ID checksum (Luhn), DOB / sex / citizenship encoded in the ID number vs form, barcode vs form, printed card vs barcode, liveness challenge, anti-spoof score, face match (cosine similarity, MobileFaceNet).

Everything runs on the phone; nothing is uploaded or stored. No Home Affairs check yet.

## Stack
Kotlin, CameraX, ML Kit (barcode, text recognition, face detection), TensorFlow Lite.
Face models: [Android-MobileFaceNet-MTCNN-FaceAntiSpoofing](https://github.com/syaringan357/Android-MobileFaceNet-MTCNN-FaceAntiSpoofing) (MIT) - downloaded at build time (checksums pinned in the workflow).

## Build
GitHub Actions (`.github/workflows/horkos-apk-build.yml`) builds on every push to `horkos/` and publishes a pre-release tagged `horkos-v0.1.N`.

Locally: put the two `.tflite` files in `android/app/src/main/assets/`, create `android/app/horkos-test.jks` (see the workflow's keytool command), then `cd android && gradle :app:assembleRelease`.

## Known limits (test version)
- Barcode is unsigned plain text - it proves consistency, not authenticity.
- Face match threshold (0.55) and anti-spoof threshold (0.2) are untuned; adjust in `FaceModels.kt` after testing on real cards.
- Without a `HORKOS_KEYSTORE_B64` secret, each build is signed with a new throwaway key, so uninstall the old build before installing a new one.
- Criminal record, ID data and face images are special personal information under POPIA - get consent before using with real people.
