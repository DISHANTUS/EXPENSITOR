import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'voice_service.dart';

/// One TTS voice installed on the device (flutter_tts getVoices). Device-specific
/// — a name on one phone may not exist on another, which is fine: we apply it if
/// present and fall back to the system default otherwise.
class DeviceVoice {
  const DeviceVoice({required this.name, required this.locale});

  final String name;
  final String locale;

  /// A friendlier label than the raw engine id (e.g. "en-us-x-sfg#female_1-local").
  String get label {
    var n = name;
    final hash = n.indexOf('#');
    if (hash > 0) n = n.substring(hash + 1);
    n = n.replaceAll('-local', '').replaceAll('-network', '').replaceAll(RegExp(r'[#_]'), ' ').trim();
    return n.isEmpty ? name : n;
  }

  @override
  bool operator ==(Object other) =>
      other is DeviceVoice && other.name == name && other.locale == locale;

  @override
  int get hashCode => Object.hash(name, locale);
}

/// The device's installed voices, sorted with the user's likely language first.
/// Empty on platforms/engines that don't enumerate voices (or in tests).
final availableVoicesProvider = FutureProvider.autoDispose<List<DeviceVoice>>((ref) async {
  final engine = ref.watch(ttsEngineProvider);
  if (engine is! FlutterTtsEngine) return const [];
  final voices = await engine.listVoices();
  voices.sort((a, b) {
    final byLocale = a.locale.toLowerCase().compareTo(b.locale.toLowerCase());
    return byLocale != 0 ? byLocale : a.label.toLowerCase().compareTo(b.label.toLowerCase());
  });
  return voices;
});
