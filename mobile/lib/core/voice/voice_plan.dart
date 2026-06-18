// How the companion SPEAKS (Sprint 5b) — mirrors the backend VoicePlan.
// Facts stay deterministic; this only carries delivery + paced segments.

class VoicePlan {
  const VoicePlan({
    this.profile = 'neutral',
    this.intensity = 'low',
    this.lead,
    this.deterministicSegments = const [],
    this.narratedSegments = const [],
    this.signature = '',
    this.autoPlay = false,
  });

  final String profile;        // neutral | concerned | warm | celebration | gentle
  final String intensity;      // low | medium | high
  final String? lead;          // spoken first, then a pause (celebration: "Congratulations!")
  final List<String> deterministicSegments;
  final List<String> narratedSegments;  // optional Ollama rewording; empty offline
  final String signature;      // time-stable dedup key (voice memory)
  final bool autoPlay;         // high-priority only; else tap-to-hear

  /// Prefer the Ollama-reworded segments when present; else deterministic.
  List<String> get segments =>
      narratedSegments.isNotEmpty ? narratedSegments : deterministicSegments;

  bool get isEmpty =>
      (lead ?? '').trim().isEmpty && segments.every((s) => s.trim().isEmpty);

  factory VoicePlan.fromJson(Map<String, dynamic> j) => VoicePlan(
        profile: (j['profile'] ?? 'neutral').toString(),
        intensity: (j['intensity'] ?? 'low').toString(),
        lead: j['lead']?.toString(),
        deterministicSegments:
            ((j['deterministic_segments'] as List?) ?? const []).map((e) => e.toString()).toList(),
        narratedSegments:
            ((j['narrated_segments'] as List?) ?? const []).map((e) => e.toString()).toList(),
        signature: (j['signature'] ?? '').toString(),
        autoPlay: j['auto_play'] == true,
      );
}
