// Mood DTOs (4c-A). Mirrors the backend MoodState envelope.

import '../voice/voice_plan.dart';
import 'reaction.dart';

String? _s(dynamic v) => v?.toString();

class MoodFace {
  const MoodFace({required this.id, required this.emoji, required this.label, this.kind = '', this.priority = 0});
  factory MoodFace.fromJson(Map<String, dynamic> j) => MoodFace(
        id: _s(j['id']) ?? '', emoji: _s(j['emoji']) ?? '🙂', label: _s(j['label']) ?? '',
        kind: _s(j['kind']) ?? '', priority: (j['priority'] as num?)?.toInt() ?? 0,
      );
  final String id;
  final String emoji;
  final String label;
  final String kind;
  final int priority;
}

class MoodReason {
  const MoodReason({required this.label, required this.value});
  factory MoodReason.fromJson(Map<String, dynamic> j) =>
      MoodReason(label: _s(j['label']) ?? '', value: _s(j['value']) ?? '');
  final String label;
  final String value;
}

class GreetingReason {
  const GreetingReason({required this.label, this.detail = ''});
  factory GreetingReason.fromJson(Map<String, dynamic> j) =>
      GreetingReason(label: _s(j['label']) ?? '', detail: _s(j['detail']) ?? '');
  final String label;
  final String detail;
}

class Greeting {
  const Greeting({
    required this.salutation,
    this.lines = const [],
    required this.category,
    this.summary = '',
    this.reasons = const [],
    this.specialDay,
    this.tone = '',
    this.displayText = '',
    this.spokenText = '',
    this.narrationSource = 'deterministic',
    this.pendingNarration = false,
    this.voice,
  });
  factory Greeting.fromJson(Map<String, dynamic> j) => Greeting(
        salutation: _s(j['salutation']) ?? '',
        lines: ((j['lines'] as List?) ?? const []).map((e) => e.toString()).toList(),
        category: _s(j['category']) ?? 'neutral',
        summary: _s(j['summary']) ?? '',
        reasons: ((j['reasons'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => GreetingReason.fromJson(e.cast<String, dynamic>()))
            .toList(),
        specialDay: _s(j['special_day']),
        tone: _s(j['tone']) ?? '',
        displayText: _s(j['display_text']) ?? '',
        spokenText: _s(j['spoken_text']) ?? '',
        narrationSource: _s(j['narration_source']) ?? 'deterministic',
        pendingNarration: j['pending_narration'] == true,
        voice: j['voice'] is Map ? VoicePlan.fromJson((j['voice'] as Map).cast<String, dynamic>()) : null,
      );
  final String salutation;
  final List<String> lines;
  final String category;
  final String summary;
  final List<GreetingReason> reasons;
  final String? specialDay;
  final String tone;
  final String displayText;     // narrated when Ollama, else salutation + lines
  final String spokenText;      // plain, for Sprint 5 TTS
  final String narrationSource; // deterministic | ollama
  final bool pendingNarration;  // a richer narrated version is being generated
  final VoicePlan? voice;       // paced, mood-aware delivery (5b)
}

class MoodState {
  const MoodState({
    required this.primary,
    required this.base,
    required this.rotation,
    this.reasons = const [],
    required this.moodWord,
    this.presenceScore = 0,
    this.presenceBand = 'new',
    this.greeting,
    this.pendingReactions = const [],
    this.companionName,
  });
  factory MoodState.fromJson(Map<String, dynamic> j) => MoodState(
        primary: MoodFace.fromJson((j['primary'] as Map).cast<String, dynamic>()),
        base: MoodFace.fromJson((j['base'] as Map).cast<String, dynamic>()),
        rotation: ((j['rotation'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => MoodFace.fromJson(e.cast<String, dynamic>()))
            .toList(),
        reasons: ((j['reasons'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => MoodReason.fromJson(e.cast<String, dynamic>()))
            .toList(),
        moodWord: _s(j['mood_word']) ?? '',
        presenceScore: (j['presence_score'] as num?)?.toInt() ?? 0,
        presenceBand: _s(j['presence_band']) ?? 'new',
        greeting: j['greeting'] is Map ? Greeting.fromJson((j['greeting'] as Map).cast<String, dynamic>()) : null,
        pendingReactions: ((j['pending_reactions'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => CompanionReaction.fromJson(e.cast<String, dynamic>()))
            .toList(),
        companionName: j['companion_name']?.toString(),
      );
  final MoodFace primary;
  final MoodFace base;
  final List<MoodFace> rotation;
  final List<MoodReason> reasons;
  final String moodWord;
  final int presenceScore;
  final String presenceBand;
  final Greeting? greeting;
  final List<CompanionReaction> pendingReactions;
  final String? companionName;   // the companion's name (6c), if set
}
