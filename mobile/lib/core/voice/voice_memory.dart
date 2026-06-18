import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Remembers what was last spoken so the companion doesn't auto-repeat the same
/// greeting on every screen/app open. Two modes:
///  * [alreadySpoken]/[markSpoken] — once-per-session/run (reactions).
///  * [spokenRecently]/[markSpokenAt] — time-windowed (greetings): suppress the
///    same signature within ~10 min, so "Good evening" isn't replayed 5×.
class VoiceMemory {
  VoiceMemory(this._storage);
  final FlutterSecureStorage _storage;
  final Set<String> _session = {};
  final Map<String, DateTime> _times = {};
  static const _key = 'voice.last_spoken';
  static const _keyTimed = 'voice.last_spoken_at';

  Future<bool> alreadySpoken(String signature) async {
    if (signature.isEmpty || _session.contains(signature)) return true;
    try {
      return (await _storage.read(key: _key)) == signature;
    } catch (_) {
      return false;   // storage unavailable -> session dedup only
    }
  }

  Future<void> markSpoken(String signature) async {
    if (signature.isEmpty) return;
    _session.add(signature);
    try {
      await _storage.write(key: _key, value: signature);
    } catch (_) {/* session set still prevents repeats this run */}
  }

  /// True if [signature] was spoken within [within] (in-memory or persisted).
  Future<bool> spokenRecently(String signature, {Duration within = const Duration(minutes: 10)}) async {
    if (signature.isEmpty) return false;
    final t = _times[signature];
    if (t != null && DateTime.now().difference(t) < within) return true;
    try {
      final raw = await _storage.read(key: _keyTimed);
      if (raw != null) {
        final i = raw.indexOf('|');
        if (i > 0 && raw.substring(0, i) == signature) {
          final ts = DateTime.tryParse(raw.substring(i + 1));
          if (ts != null && DateTime.now().difference(ts) < within) return true;
        }
      }
    } catch (_) {/* storage unavailable -> in-memory only */}
    return false;
  }

  Future<void> markSpokenAt(String signature) async {
    if (signature.isEmpty) return;
    final now = DateTime.now();
    _times[signature] = now;
    try {
      await _storage.write(key: _keyTimed, value: '$signature|${now.toIso8601String()}');
    } catch (_) {/* in-memory map still suppresses repeats this run */}
  }
}

final voiceMemoryProvider = Provider<VoiceMemory>((_) => VoiceMemory(const FlutterSecureStorage()));
