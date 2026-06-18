// Future Me DTOs (Sprint 6b) — mirrors the backend FutureMeView.

class FutureMePath {
  const FutureMePath({required this.mode, required this.label, this.eta, this.monthlyRate = '', this.narrative = ''});
  final String mode;          // current | optimistic | conservative
  final String label;
  final String? eta;          // ISO date, or null when not reachable at this rate
  final String monthlyRate;
  final String narrative;

  factory FutureMePath.fromJson(Map<String, dynamic> j) => FutureMePath(
        mode: (j['mode'] ?? '').toString(),
        label: (j['label'] ?? '').toString(),
        eta: j['eta']?.toString(),
        monthlyRate: (j['monthly_rate'] ?? '').toString(),
        narrative: (j['narrative'] ?? '').toString(),
      );
}

class FutureMeLever {
  const FutureMeLever({required this.label, required this.ref});
  final String label;
  final String ref;
  factory FutureMeLever.fromJson(Map<String, dynamic> j) =>
      FutureMeLever(label: (j['label'] ?? '').toString(), ref: (j['ref'] ?? '').toString());
}

class FutureMeMilestone {
  const FutureMeMilestone({required this.title, this.date, this.detail = '', this.kind = 'forecast', this.icon = '•'});
  final String title;
  final String? date;
  final String detail;
  final String kind;
  final String icon;
  factory FutureMeMilestone.fromJson(Map<String, dynamic> j) => FutureMeMilestone(
        title: (j['title'] ?? '').toString(),
        date: j['date']?.toString(),
        detail: (j['detail'] ?? '').toString(),
        kind: (j['kind'] ?? 'forecast').toString(),
        icon: (j['icon'] ?? '•').toString(),
      );
}

class FutureMeView {
  const FutureMeView({
    this.headline = '',
    this.confidence = 'insufficient',
    this.reasoning = '',
    this.currency = '',
    this.paths = const [],
    this.levers = const [],
    this.milestones = const [],
  });

  final String headline;
  final String confidence;
  final String reasoning;
  final String currency;
  final List<FutureMePath> paths;
  final List<FutureMeLever> levers;
  final List<FutureMeMilestone> milestones;

  factory FutureMeView.fromJson(Map<String, dynamic> j) => FutureMeView(
        headline: (j['headline'] ?? '').toString(),
        confidence: (j['confidence'] ?? 'insufficient').toString(),
        reasoning: (j['reasoning'] ?? '').toString(),
        currency: (j['currency'] ?? '').toString(),
        paths: ((j['paths'] as List?) ?? const [])
            .whereType<Map>().map((e) => FutureMePath.fromJson(e.cast<String, dynamic>())).toList(),
        levers: ((j['levers'] as List?) ?? const [])
            .whereType<Map>().map((e) => FutureMeLever.fromJson(e.cast<String, dynamic>())).toList(),
        milestones: ((j['milestones'] as List?) ?? const [])
            .whereType<Map>().map((e) => FutureMeMilestone.fromJson(e.cast<String, dynamic>())).toList(),
      );
}
