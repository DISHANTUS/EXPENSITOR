import 'dart:async';

import 'package:expensitor_mobile/core/companion/reaction.dart';
import 'package:expensitor_mobile/core/voice/voice_memory.dart';
import 'package:expensitor_mobile/core/voice/voice_plan.dart';
import 'package:expensitor_mobile/core/voice/voice_service.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

/// A fake TTS engine — records calls, lets the test drive completion/cancel.
class FakeTts implements TtsEngine {
  final List<String> spoken = [];
  bool stopped = false;
  void Function()? _onComplete;
  void Function()? _onCancel;

  @override
  Future<void> configure() async {}
  @override
  Future<void> setStyle({required double rate, required double pitch, double volume = 1.0}) async {}
  @override
  Future<void> speak(String text) async => spoken.add(text);
  @override
  Future<void> stop() async {
    stopped = true;
    _onCancel?.call();
  }

  @override
  set onComplete(void Function()? cb) => _onComplete = cb;
  @override
  set onCancel(void Function()? cb) => _onCancel = cb;

  void finishSpeaking() => _onComplete?.call();
}

/// Like FakeTts, but each speak() blocks on a gate the test releases — so we can
/// interrupt a paced sequence mid-flight.
class GatedTts implements TtsEngine {
  final List<String> spoken = [];
  Completer<void>? _gate;

  @override
  Future<void> configure() async {}
  @override
  Future<void> setStyle({required double rate, required double pitch, double volume = 1.0}) async {}
  @override
  Future<void> speak(String text) {
    spoken.add(text);
    return (_gate = Completer<void>()).future;
  }

  @override
  Future<void> stop() async {}
  @override
  set onComplete(void Function()? cb) {}
  @override
  set onCancel(void Function()? cb) {}

  void release() {
    _gate?.complete();
    _gate = null;
  }
}

Future<void> _settle() async {
  for (var i = 0; i < 8; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  group('VoiceController (5a basics)', () {
    test('speak sets speaking state and forwards text', () async {
      final tts = FakeTts();
      final c = VoiceController(tts);
      await c.speak('Good evening.');
      expect(c.state, VoiceState.speaking);
      expect(tts.spoken.single, 'Good evening.');
    });

    test('empty text is ignored', () async {
      final c = VoiceController(FakeTts());
      await c.speak('   ');
      expect(c.state, VoiceState.idle);
    });

    test('completion handler returns to idle', () async {
      final tts = FakeTts();
      final c = VoiceController(tts);
      await c.speak('hello');
      tts.finishSpeaking();
      expect(c.state, VoiceState.idle);
    });

    test('toggle: speaks when idle, stops when speaking', () async {
      final tts = FakeTts();
      final c = VoiceController(tts);
      await c.toggle('hi');
      expect(c.state, VoiceState.speaking);
      await c.toggle('hi');
      expect(tts.stopped, isTrue);
      expect(c.state, VoiceState.idle);
    });
  });

  group('paced speakPlan (5b)', () {
    test('speaks the lead first, then each segment in order', () async {
      final tts = FakeTts();
      final c = VoiceController(tts);
      await c.speakPlan(const VoicePlan(
        profile: 'celebration', intensity: 'high', lead: 'Congratulations!',
        deterministicSegments: ['You completed your Japan goal.', 'A real milestone.'],
      ));
      expect(tts.spoken, ['Congratulations!', 'You completed your Japan goal.', 'A real milestone.']);
      expect(c.state, VoiceState.idle);
    });

    test('prefers narrated segments over deterministic', () async {
      final tts = FakeTts();
      final c = VoiceController(tts);
      await c.speakPlan(const VoicePlan(
        deterministicSegments: ['Your salary should arrive today.'],
        narratedSegments: ['Your pay lands today.'],
      ));
      expect(tts.spoken, ['Your pay lands today.']);
    });

    test('stop() mid-sequence aborts the remaining segments', () async {
      final tts = GatedTts();
      final c = VoiceController(tts);
      final fut = c.speakPlan(const VoicePlan(deterministicSegments: ['a', 'b', 'c']));
      await _settle();
      expect(tts.spoken, ['a']);          // blocked on the first segment's gate
      await c.stop();                     // bump generation -> sequence should bail
      tts.release();                      // first speak completes
      await fut;
      expect(tts.spoken, ['a']);          // 'b' and 'c' never spoken
      expect(c.state, VoiceState.idle);
    });
  });

  group('VoiceProfile mapping (5b)', () {
    test('concerned is slower and lower than neutral; celebration is faster', () {
      final neutral = VoiceProfile.from('neutral', 'low');
      final concerned = VoiceProfile.from('concerned', 'medium');
      final celebration = VoiceProfile.from('celebration', 'high');
      expect(concerned.rate, lessThan(neutral.rate));
      expect(concerned.pitch, lessThan(neutral.pitch));
      expect(celebration.rate, greaterThan(neutral.rate));
    });

    test('higher intensity lengthens concerned pauses', () {
      final mid = VoiceProfile.from('concerned', 'medium');
      final high = VoiceProfile.from('concerned', 'high');
      expect(high.gapPause, greaterThan(mid.gapPause));
    });
  });

  group('reaction voice plans (5b)', () {
    test('achievement -> celebration, auto-play, "Congratulations!" lead', () {
      final p = const CompanionReaction(
        kind: 'achievement', emoji: '🏆', headline: 'Achievement unlocked!',
        detail: 'Japan goal', importance: ReactionImportance.achievement,
      ).voicePlan;
      expect(p.profile, 'celebration');
      expect(p.autoPlay, isTrue);
      expect(p.lead, 'Congratulations!');
      expect(p.intensity, 'high');
    });

    test('loan_repaid milestone leads with "Good news!"', () {
      expect(reactionFor('loan_repaid').voicePlan.lead, 'Good news!');
    });

    test('normal income ack is neutral, no lead, never auto-plays', () {
      final p = reactionFor('income').voicePlan;
      expect(p.profile, 'neutral');
      expect(p.autoPlay, isFalse);
      expect(p.lead, isNull);
    });
  });

  group('VoiceMemory (5a + 5b timed dedup)', () {
    test('session dedup (reactions)', () async {
      final mem = VoiceMemory(const FlutterSecureStorage());
      const sig = 'rx:income|Nice';
      expect(await mem.alreadySpoken(sig), isFalse);
      await mem.markSpoken(sig);
      expect(await mem.alreadySpoken(sig), isTrue);
      expect(await mem.alreadySpoken('different'), isFalse);
    });

    test('timed dedup suppresses the same greeting signature within the window', () async {
      final mem = VoiceMemory(const FlutterSecureStorage());
      const sig = 'greet:2026-06-17:evening';
      expect(await mem.spokenRecently(sig), isFalse);
      await mem.markSpokenAt(sig);
      expect(await mem.spokenRecently(sig), isTrue);                 // won't replay "Good evening" 5x
      expect(await mem.spokenRecently('greet:2026-06-17:morning'), isFalse);
    });
  });
}
