import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';

import 'voice_plan.dart';

/// The companion's speaking state (drives the mic toggle + speaking animation).
enum VoiceState { idle, speaking, paused, stopped }

/// A thin, injectable TTS abstraction so the controller is testable with no engine.
abstract class TtsEngine {
  Future<void> configure();
  Future<void> setStyle({required double rate, required double pitch, double volume = 1.0});
  Future<void> speak(String text);
  Future<void> stop();
  set onComplete(void Function()? cb);
  set onCancel(void Function()? cb);
}

/// flutter_tts-backed engine (native, offline — no API). Sprint 5a/5b.
class FlutterTtsEngine implements TtsEngine {
  final FlutterTts _tts = FlutterTts();
  bool _configured = false;

  @override
  Future<void> configure() async {
    if (_configured) return;
    _configured = true;
    await _tts.awaitSpeakCompletion(true);   // so paced segments can await completion (5b)
  }

  @override
  Future<void> setStyle({required double rate, required double pitch, double volume = 1.0}) async {
    await _tts.setSpeechRate(rate);
    await _tts.setPitch(pitch);
    await _tts.setVolume(volume);
  }

  @override
  Future<void> speak(String text) => _tts.speak(text);

  @override
  Future<void> stop() => _tts.stop();

  @override
  set onComplete(void Function()? cb) => _tts.setCompletionHandler(cb ?? () {});

  @override
  set onCancel(void Function()? cb) {
    _tts.setCancelHandler(cb ?? () {});
    _tts.setErrorHandler((_) => (cb ?? () {})());
  }
}

/// Maps a VoicePlan profile + intensity to concrete flutter_tts delivery: rate,
/// pitch, volume, and the pauses between segments. Same words, different feel.
class VoiceProfile {
  const VoiceProfile({
    required this.rate,
    required this.pitch,
    this.volume = 1.0,
    this.leadPause = const Duration(milliseconds: 450),
    this.gapPause = const Duration(milliseconds: 320),
  });

  final double rate;
  final double pitch;
  final double volume;
  final Duration leadPause;   // after the celebration lead
  final Duration gapPause;    // between sentences

  factory VoiceProfile.from(String profile, String intensity) {
    var rate = 0.5, pitch = 1.0, vol = 1.0;
    var gap = 320, lead = 450;
    switch (profile) {
      case 'concerned':                    // slower, softer, slightly lower
        rate = 0.42; pitch = 0.92; vol = 0.9; gap = 420;
      case 'warm':                         // normal speed, warmer pitch
        rate = 0.48; pitch = 1.06;
      case 'celebration':                  // faster, more energetic, celebration pause
        rate = 0.56; pitch = 1.12; gap = 260; lead = 550;
      case 'gentle':                       // late-night: unhurried, quiet
        rate = 0.44; pitch = 0.98; vol = 0.85; gap = 380;
      default:                             // neutral
        break;
    }
    switch (intensity) {                   // same profile, different pacing
      case 'high':
        if (profile == 'concerned') { rate -= 0.04; gap = 540; }       // sound more serious
        else if (profile == 'celebration') { rate += 0.04; pitch += 0.04; }
      case 'low':
        gap = (gap * 0.8).round();
      default:
        break;
    }
    return VoiceProfile(
      rate: rate.clamp(0.2, 1.0),
      pitch: pitch.clamp(0.5, 2.0),
      volume: vol.clamp(0.0, 1.0),
      leadPause: Duration(milliseconds: lead),
      gapPause: Duration(milliseconds: gap),
    );
  }
}

/// Owns the speaking state. Mic = a single toggle: tap speaks, tap-while-speaking
/// stops, tap again speaks. Always interruptible — including mid-sequence.
class VoiceController extends StateNotifier<VoiceState> {
  VoiceController(this._tts) : super(VoiceState.idle) {
    _tts.onComplete = _settleIdle;
    _tts.onCancel = _settleIdle;
  }
  final TtsEngine _tts;
  int _gen = 0;   // bumped on stop() so an in-flight paced sequence aborts

  bool get isSpeaking => state == VoiceState.speaking;

  void _settleIdle() {
    if (mounted && state == VoiceState.speaking) state = VoiceState.idle;
  }

  Future<void> speak(String text, {double rate = 0.5, double pitch = 1.0}) async {
    final t = text.trim();
    if (t.isEmpty) return;
    await _tts.configure();
    await _tts.setStyle(rate: rate, pitch: pitch);
    state = VoiceState.speaking;
    try {
      await _tts.speak(t);
    } catch (_) {
      if (mounted) state = VoiceState.idle;
    }
  }

  /// Speak a plan: optional lead, then each segment, with mood/intensity-driven
  /// pauses. Cancellable — stop() or a new plan aborts the sequence cleanly.
  Future<void> speakPlan(VoicePlan plan) async {
    await stop();
    final p = VoiceProfile.from(plan.profile, plan.intensity);
    final hasLead = (plan.lead ?? '').trim().isNotEmpty;
    final utterances = <String>[
      if (hasLead) plan.lead!.trim(),
      ...plan.segments.map((s) => s.trim()).where((s) => s.isNotEmpty),
    ];
    if (utterances.isEmpty) return;
    await _tts.configure();
    await _tts.setStyle(rate: p.rate, pitch: p.pitch, volume: p.volume);
    final myGen = ++_gen;
    if (!mounted) return;
    state = VoiceState.speaking;
    for (var i = 0; i < utterances.length; i++) {
      if (!mounted || myGen != _gen) return;            // interrupted
      try {
        await _tts.speak(utterances[i]);
      } catch (_) {
        break;
      }
      if (myGen != _gen) return;
      if (i < utterances.length - 1) {
        await Future<void>.delayed(i == 0 && hasLead ? p.leadPause : p.gapPause);
      }
    }
    if (mounted && myGen == _gen && state == VoiceState.speaking) state = VoiceState.idle;
  }

  Future<void> stop() async {
    _gen++;                                             // cancel any paced sequence
    await _tts.stop();
    if (mounted) state = VoiceState.idle;
  }

  /// The mic-button behaviour for plain text.
  Future<void> toggle(String text, {double rate = 0.5, double pitch = 1.0}) async {
    if (isSpeaking) {
      await stop();
    } else {
      await speak(text, rate: rate, pitch: pitch);
    }
  }

  /// The mic-button behaviour for a VoicePlan (paced, mood-aware).
  Future<void> togglePlan(VoicePlan plan) async {
    if (isSpeaking) {
      await stop();
    } else {
      await speakPlan(plan);
    }
  }
}

final ttsEngineProvider = Provider<TtsEngine>((_) => FlutterTtsEngine());

final voiceControllerProvider = StateNotifierProvider<VoiceController, VoiceState>(
  (ref) => VoiceController(ref.watch(ttsEngineProvider)),
);
