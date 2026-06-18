import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// Injectable speech-to-text so the conversation loop is testable with no device.
abstract class SttEngine {
  Future<bool> initialize();
  bool get isAvailable;
  Future<void> listen({
    required void Function(String text, bool isFinal) onResult,
    void Function()? onDone,
  });
  Future<void> stop();
  Future<void> cancel();
}

/// speech_to_text-backed engine — uses the device's on-device/Google recognizer.
class SpeechToTextEngine implements SttEngine {
  final SpeechToText _stt = SpeechToText();
  bool _available = false;
  void Function()? _onDone;

  @override
  bool get isAvailable => _available;

  @override
  Future<bool> initialize() async {
    if (_available) return true;
    try {
      _available = await _stt.initialize(
        onStatus: (s) {
          if (s == 'done' || s == 'notListening') _onDone?.call();
        },
        onError: (_) => _onDone?.call(),
      );
    } catch (_) {
      _available = false;
    }
    return _available;
  }

  @override
  Future<void> listen({
    required void Function(String text, bool isFinal) onResult,
    void Function()? onDone,
  }) async {
    _onDone = onDone;
    try {
      await _stt.listen(
        onResult: (r) => onResult(r.recognizedWords, r.finalResult),
        listenOptions: SpeechListenOptions(
          partialResults: true,
          cancelOnError: true,
          listenFor: const Duration(seconds: 30),
          pauseFor: const Duration(seconds: 3),
        ),
      );
    } catch (_) {
      _onDone?.call();
    }
  }

  @override
  Future<void> stop() async {
    try {
      await _stt.stop();
    } catch (_) {/* ignore */}
  }

  @override
  Future<void> cancel() async {
    try {
      await _stt.cancel();
    } catch (_) {/* ignore */}
  }
}

final sttEngineProvider = Provider<SttEngine>((_) => SpeechToTextEngine());
