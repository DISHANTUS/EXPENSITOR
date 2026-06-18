// Relationship-page DTOs (Sprint 7) — mirrors the backend relationship schemas.

import '../timeline/timeline_models.dart';

class TrustProfile {
  const TrustProfile({required this.label, this.repaid = 0, this.total = 0, this.outstanding});
  final String label;       // Reliable | Repaying | Owes you
  final int repaid;
  final int total;
  final String? outstanding;

  factory TrustProfile.fromJson(Map<String, dynamic> j) => TrustProfile(
        label: (j['label'] ?? '').toString(),
        repaid: (j['repaid'] as num?)?.toInt() ?? 0,
        total: (j['total'] as num?)?.toInt() ?? 0,
        outstanding: j['outstanding']?.toString(),
      );
}

class RelationshipSummary {
  const RelationshipSummary({
    required this.name,
    this.relationshipType,
    this.memoryCount = 0,
    this.futureCount = 0,
    this.reliability,
  });
  final String name;
  final String? relationshipType;
  final int memoryCount;
  final int futureCount;
  final String? reliability;

  factory RelationshipSummary.fromJson(Map<String, dynamic> j) => RelationshipSummary(
        name: (j['name'] ?? '').toString(),
        relationshipType: j['relationship_type']?.toString(),
        memoryCount: (j['memory_count'] as num?)?.toInt() ?? 0,
        futureCount: (j['future_count'] as num?)?.toInt() ?? 0,
        reliability: j['reliability']?.toString(),
      );
}

class RelationshipDetail {
  const RelationshipDetail({
    required this.name,
    this.relationshipType,
    this.trustNote = '',
    this.companionNote = '',
    this.timeline = const [],
    this.future = const [],
    this.memories = const [],
    this.trust,
  });

  final String name;
  final String? relationshipType;
  final String trustNote;
  final String companionNote;
  final List<TimelineEntry> timeline;
  final List<TimelineEntry> future;
  final List<String> memories;
  final TrustProfile? trust;

  factory RelationshipDetail.fromJson(Map<String, dynamic> j) => RelationshipDetail(
        name: (j['name'] ?? '').toString(),
        relationshipType: j['relationship_type']?.toString(),
        trustNote: (j['trust_note'] ?? '').toString(),
        companionNote: (j['companion_note'] ?? '').toString(),
        timeline: ((j['timeline'] as List?) ?? const [])
            .whereType<Map>().map((e) => TimelineEntry.fromJson(e.cast<String, dynamic>())).toList(),
        future: ((j['future'] as List?) ?? const [])
            .whereType<Map>().map((e) => TimelineEntry.fromJson(e.cast<String, dynamic>())).toList(),
        memories: ((j['memories'] as List?) ?? const []).map((e) => e.toString()).toList(),
        trust: j['trust'] is Map ? TrustProfile.fromJson((j['trust'] as Map).cast<String, dynamic>()) : null,
      );
}
