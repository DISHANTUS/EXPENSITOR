import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:image_picker/image_picker.dart';

/// Turns a photo of a receipt into raw text, on-device.
///
/// Everything here is native and cannot be exercised in a unit test — the
/// camera, the gallery and ML Kit's recognizer only exist on a real device. So
/// it's deliberately thin and isolated: it either returns text or null, and
/// never throws into the caller. The text it produces is handed to the
/// already-tested backend receipt parser; the intelligence lives there, not
/// here.
///
/// On-device and offline: ML Kit's Latin text recognition runs locally, so a
/// receipt never leaves the phone as an image — only the text the user then
/// confirms becomes an expense. No cloud OCR, no per-scan cost, fits the
/// no-paid-service rule.
class ReceiptScanService {
  ReceiptScanService({ImagePicker? picker}) : _picker = picker ?? ImagePicker();

  final ImagePicker _picker;

  /// Photograph or pick a receipt and return the recognized text, or null if
  /// the user cancelled or nothing could be read. Never throws.
  Future<String?> scanText({bool fromCamera = true}) async {
    TextRecognizer? recognizer;
    try {
      final XFile? photo = await _picker.pickImage(
        source: fromCamera ? ImageSource.camera : ImageSource.gallery,
        imageQuality: 85,
      );
      if (photo == null) return null; // user backed out

      recognizer = TextRecognizer(script: TextRecognitionScript.latin);
      final recognized = await recognizer.processImage(InputImage.fromFilePath(photo.path));
      final text = recognized.text.trim();
      return text.isEmpty ? null : text;
    } catch (_) {
      // Camera denied, ML Kit hiccup, unreadable image — all just mean "no
      // scan". The manual add path is always there; a scan failure is never an
      // error the user has to deal with.
      return null;
    } finally {
      await recognizer?.close();
    }
  }
}

final receiptScanServiceProvider = Provider<ReceiptScanService>((ref) => ReceiptScanService());
