// Dashboard DTOs — parse only what the Home screen renders, defensively
// (every field tolerates nulls so a thin/cold-start backend response is safe).

String? _s(dynamic v) => v?.toString();

class ProactiveItem {
  const ProactiveItem({
    required this.kind,
    required this.category,
    required this.title,
    required this.whatHappened,
    required this.whyItMatters,
    required this.whatNext,
    required this.severity,
    this.mostUsefulNumber,
  });

  factory ProactiveItem.fromJson(Map<String, dynamic> j) => ProactiveItem(
        kind: _s(j['kind']) ?? 'info',
        category: _s(j['category']) ?? '',
        title: _s(j['title']) ?? '',
        whatHappened: _s(j['what_happened']) ?? '',
        whyItMatters: _s(j['why_it_matters']) ?? '',
        whatNext: _s(j['what_next']) ?? '',
        severity: _s(j['severity']) ?? 'info',
        mostUsefulNumber: _s(j['most_useful_number']),
      );

  final String kind;
  final String category;
  final String title;
  final String whatHappened;
  final String whyItMatters;
  final String whatNext;
  final String severity;
  final String? mostUsefulNumber;
}

class ProactiveFeed {
  const ProactiveFeed({required this.mostImportant, required this.items});

  factory ProactiveFeed.fromJson(Map<String, dynamic> j) {
    final raw = (j['items'] as List?) ?? const [];
    final items = raw.whereType<Map>().map((e) => ProactiveItem.fromJson(e.cast<String, dynamic>())).toList();
    final mi = j['most_important'];
    return ProactiveFeed(
      mostImportant: mi is Map ? ProactiveItem.fromJson(mi.cast<String, dynamic>()) : null,
      items: items,
    );
  }

  final ProactiveItem? mostImportant;
  final List<ProactiveItem> items;

  /// Everything except the headline item (the feed ranks most_important first).
  List<ProactiveItem> get others {
    if (mostImportant == null || items.isEmpty) return items;
    return items.where((i) => !identical(i, items.first)).toList();
  }
}

class SpentCategory {
  const SpentCategory({required this.label, required this.amount});
  factory SpentCategory.fromJson(Map<String, dynamic> j) =>
      SpentCategory(label: _s(j['label']) ?? '', amount: (j['amount'] as num?)?.toDouble() ?? 0);
  final String label;
  final double amount;
}

/// Actual today-spend, by category — distinct from [DailyBrief.dailyRemaining],
/// which is a forward-looking allowance, not a sum of what's already spent.
class TodaySnapshot {
  const TodaySnapshot({required this.currency, required this.spentToday, this.byCategory = const []});
  factory TodaySnapshot.fromJson(Map<String, dynamic> j) => TodaySnapshot(
        currency: _s(j['currency']) ?? 'INR',
        spentToday: (j['spent_today'] as num?)?.toDouble() ?? 0,
        byCategory: ((j['spent_today_by_category'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => SpentCategory.fromJson(e.cast<String, dynamic>()))
            .toList(),
      );
  final String currency;
  final double spentToday;
  final List<SpentCategory> byCategory;
}

class DailyBrief {
  const DailyBrief({
    required this.currency,
    this.dailyRemaining,
    this.weeklyRemaining,
    this.monthlyDiscretionaryRemaining,
    this.headline,
    this.paragraphs = const [],
    this.severity,
    this.today,
  });

  factory DailyBrief.fromJson(Map<String, dynamic> j) {
    final ctx = (j['context'] as Map?)?.cast<String, dynamic>() ?? const {};
    final det = ((j['commentary'] as Map?)?['deterministic_commentary'] as Map?)?.cast<String, dynamic>();
    final paras = (det?['paragraphs'] as List?)?.map((e) => e.toString()).toList() ?? const <String>[];
    final snap = (j['today_snapshot'] as Map?)?.cast<String, dynamic>();
    return DailyBrief(
      currency: _s(ctx['currency']) ?? 'INR',
      dailyRemaining: _s(ctx['daily_remaining']),
      weeklyRemaining: _s(ctx['weekly_remaining']),
      monthlyDiscretionaryRemaining: _s(ctx['monthly_discretionary_remaining']),
      headline: _s(det?['headline']),
      paragraphs: paras,
      severity: _s(det?['severity']),
      today: snap == null ? null : TodaySnapshot.fromJson(snap),
    );
  }

  final String currency;
  final String? dailyRemaining;
  final String? weeklyRemaining;
  final String? monthlyDiscretionaryRemaining;
  final String? headline;
  final List<String> paragraphs;
  final String? severity;
  final TodaySnapshot? today;
}

class PillarSummary {
  const PillarSummary({required this.label, required this.score, required this.state});
  factory PillarSummary.fromJson(Map<String, dynamic> j) => PillarSummary(
        label: _s(j['label']) ?? _s(j['key']) ?? '',
        score: (j['score'] as num?)?.toInt() ?? 50,
        state: _s(j['state']) ?? 'fair',
      );
  final String label;
  final int score;
  final String state;
}

class HealthSummary {
  const HealthSummary({
    required this.overallScore,
    required this.overallState,
    required this.overallConfidence,
    required this.pillars,
    this.biggestDrag,
    this.topStrength,
    this.improvingArea,
    this.worseningArea,
  });

  factory HealthSummary.fromJson(Map<String, dynamic> j) {
    final pillars = ((j['pillars'] as List?) ?? const [])
        .whereType<Map>()
        .map((e) => PillarSummary.fromJson(e.cast<String, dynamic>()))
        .toList();
    final drag = j['biggest_drag'];
    final strengths = (j['top_strengths'] as List?)?.map((e) => e.toString()).toList() ?? const <String>[];
    return HealthSummary(
      overallScore: (j['overall_score'] as num?)?.toInt() ?? 50,
      overallState: _s(j['overall_state']) ?? 'fair',
      overallConfidence: _s(j['overall_confidence']) ?? 'low',
      pillars: pillars,
      biggestDrag: drag is Map ? _s(drag['statement']) : null,
      topStrength: strengths.isNotEmpty ? strengths.first : null,
      improvingArea: _s(j['improving_area']),
      worseningArea: _s(j['worsening_area']),
    );
  }

  final int overallScore;
  final String overallState;
  final String overallConfidence;
  final List<PillarSummary> pillars;
  final String? biggestDrag;
  final String? topStrength;
  final String? improvingArea;
  final String? worseningArea;

  bool get isColdStart => overallConfidence != 'normal';
}
