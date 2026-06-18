// Life Timeline DTOs (Sprint 6a) — mirrors the backend Timeline envelope.

class TimelineEntry {
  const TimelineEntry({
    required this.title,
    this.date,
    this.detail = '',
    this.kind = 'event',
    this.importance = 'medium',
    this.when = 'past',
    this.icon = '•',
    this.person,
  });

  final String title;
  final String? date;        // ISO yyyy-MM-dd (null = undated/present)
  final String detail;
  final String kind;         // achievement | goal | loan | event | lesson | income | life_event | forecast
  final String importance;   // life_milestone | high | medium | low
  final String when;         // past | present | future
  final String icon;
  final String? person;      // who this involves (7)

  bool get isFuture => when == 'future';
  bool get isMilestone => importance == 'life_milestone';

  factory TimelineEntry.fromJson(Map<String, dynamic> j) => TimelineEntry(
        title: (j['title'] ?? '').toString(),
        date: j['date']?.toString(),
        detail: (j['detail'] ?? '').toString(),
        kind: (j['kind'] ?? 'event').toString(),
        importance: (j['importance'] ?? 'medium').toString(),
        when: (j['when'] ?? 'past').toString(),
        icon: (j['icon'] ?? '•').toString(),
        person: j['person']?.toString(),
      );
}

class TimelineChapter {
  const TimelineChapter({required this.label, this.subtitle = '', this.entries = const []});
  final String label;
  final String subtitle;
  final List<TimelineEntry> entries;

  factory TimelineChapter.fromJson(Map<String, dynamic> j) => TimelineChapter(
        label: (j['label'] ?? '').toString(),
        subtitle: (j['subtitle'] ?? '').toString(),
        entries: ((j['entries'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => TimelineEntry.fromJson(e.cast<String, dynamic>()))
            .toList(),
      );
}

class TimelineSearchResult {
  const TimelineSearchResult({this.summary = '', this.entries = const []});
  final String summary;
  final List<TimelineEntry> entries;

  factory TimelineSearchResult.fromJson(Map<String, dynamic> j) => TimelineSearchResult(
        summary: (j['summary'] ?? '').toString(),
        entries: ((j['entries'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => TimelineEntry.fromJson(e.cast<String, dynamic>()))
            .toList(),
      );
}

class Timeline {
  const Timeline({
    this.chapters = const [],
    this.pastCount = 0,
    this.presentCount = 0,
    this.futureCount = 0,
    this.headline = '',
  });

  final List<TimelineChapter> chapters;
  final int pastCount;
  final int presentCount;
  final int futureCount;
  final String headline;

  bool get isEmpty => chapters.isEmpty;

  factory Timeline.fromJson(Map<String, dynamic> j) => Timeline(
        chapters: ((j['chapters'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => TimelineChapter.fromJson(e.cast<String, dynamic>()))
            .toList(),
        pastCount: (j['past_count'] as num?)?.toInt() ?? 0,
        presentCount: (j['present_count'] as num?)?.toInt() ?? 0,
        futureCount: (j['future_count'] as num?)?.toInt() ?? 0,
        headline: (j['headline'] ?? '').toString(),
      );
}
