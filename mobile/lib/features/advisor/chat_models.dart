// Conversational-advisor DTOs (4b). Mirrors the backend ChatTurn envelope.

String? _s(dynamic v) => v?.toString();

class ChatOption {
  const ChatOption({required this.label, required this.message});
  factory ChatOption.fromJson(Map<String, dynamic> j) =>
      ChatOption(label: _s(j['label']) ?? '', message: _s(j['message']) ?? '');
  final String label;
  final String message;
}

class GraphPoint {
  const GraphPoint({required this.label, required this.spent, required this.income, required this.saved});
  factory GraphPoint.fromJson(Map<String, dynamic> j) => GraphPoint(
        label: _s(j['label']) ?? '',
        spent: double.tryParse(_s(j['spent']) ?? '0') ?? 0,
        income: double.tryParse(_s(j['income']) ?? '0') ?? 0,
        saved: double.tryParse(_s(j['saved']) ?? '0') ?? 0,
      );
  final String label;
  final double spent;
  final double income;
  final double saved;
}

class GraphSeries {
  const GraphSeries({required this.granularity, required this.points});
  factory GraphSeries.fromJson(Map<String, dynamic> j) => GraphSeries(
        granularity: _s(j['granularity']) ?? 'day',
        points: ((j['points'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => GraphPoint.fromJson(e.cast<String, dynamic>()))
            .toList(),
      );
  final String granularity;
  final List<GraphPoint> points;
}

class ReportSummary {
  const ReportSummary({
    required this.currency,
    required this.totalSpent,
    required this.totalIncome,
    required this.saved,
    required this.redDays,
    required this.crownDays,
  });
  factory ReportSummary.fromJson(Map<String, dynamic> j) => ReportSummary(
        currency: _s(j['currency']) ?? 'INR',
        totalSpent: _s(j['total_spent']) ?? '0',
        totalIncome: _s(j['total_income']) ?? '0',
        saved: _s(j['saved']) ?? '0',
        redDays: (j['red_days'] as num?)?.toInt() ?? 0,
        crownDays: (j['crown_days'] as num?)?.toInt() ?? 0,
      );
  final String currency;
  final String totalSpent;
  final String totalIncome;
  final String saved;
  final int redDays;
  final int crownDays;
}

class ReportStory {
  const ReportStory({required this.beginning, required this.middle, required this.end});
  factory ReportStory.fromJson(Map<String, dynamic> j) => ReportStory(
        beginning: _s(j['beginning']) ?? '',
        middle: _s(j['middle']) ?? '',
        end: _s(j['end']) ?? '',
      );
  final String beginning;
  final String middle;
  final String end;
}

class TimelineEvent {
  const TimelineEvent({required this.label, required this.kind});
  factory TimelineEvent.fromJson(Map<String, dynamic> j) =>
      TimelineEvent(label: _s(j['label']) ?? '', kind: _s(j['kind']) ?? '');
  final String label;
  final String kind;
}

class CategoryDelta {
  const CategoryDelta({required this.label, required this.current, required this.previous, this.changePct});
  factory CategoryDelta.fromJson(Map<String, dynamic> j) => CategoryDelta(
        label: _s(j['label']) ?? '',
        current: _s(j['current']) ?? '0',
        previous: _s(j['previous']) ?? '0',
        changePct: (j['change_pct'] as num?)?.toDouble(),
      );
  final String label;
  final String current;
  final String previous;
  final double? changePct;
}

class PeriodDelta {
  const PeriodDelta({this.spentPct, this.incomePct, this.savedPct, this.biggestIncrease, this.biggestDecrease, this.categories = const []});
  factory PeriodDelta.fromJson(Map<String, dynamic> j) {
    CategoryDelta? cd(dynamic v) => v is Map ? CategoryDelta.fromJson(v.cast<String, dynamic>()) : null;
    return PeriodDelta(
      spentPct: (j['spent_change_pct'] as num?)?.toDouble(),
      incomePct: (j['income_change_pct'] as num?)?.toDouble(),
      savedPct: (j['saved_change_pct'] as num?)?.toDouble(),
      biggestIncrease: cd(j['biggest_increase']),
      biggestDecrease: cd(j['biggest_decrease']),
      categories: ((j['categories'] as List?) ?? const [])
          .whereType<Map>()
          .map((e) => CategoryDelta.fromJson(e.cast<String, dynamic>()))
          .toList(),
    );
  }
  final double? spentPct;
  final double? incomePct;
  final double? savedPct;
  final CategoryDelta? biggestIncrease;
  final CategoryDelta? biggestDecrease;
  final List<CategoryDelta> categories;
}

class ReportSession {
  const ReportSession({
    required this.periodLabel,
    required this.currency,
    required this.confidence,
    required this.series,
    required this.summary,
    required this.story,
    required this.timelineEvents,
    this.delta,
    this.comparisonLabel,
  });
  factory ReportSession.fromJson(Map<String, dynamic> j) => ReportSession(
        periodLabel: _s(j['period_label']) ?? '',
        currency: _s(j['currency']) ?? 'INR',
        confidence: _s(j['confidence']) ?? 'low',
        series: GraphSeries.fromJson((j['series'] as Map?)?.cast<String, dynamic>() ?? const {}),
        summary: ReportSummary.fromJson((j['summary'] as Map?)?.cast<String, dynamic>() ?? const {}),
        story: ReportStory.fromJson((j['story'] as Map?)?.cast<String, dynamic>() ?? const {}),
        timelineEvents: ((j['timeline_events'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => TimelineEvent.fromJson(e.cast<String, dynamic>()))
            .toList(),
        delta: j['delta'] is Map ? PeriodDelta.fromJson((j['delta'] as Map).cast<String, dynamic>()) : null,
        comparisonLabel: _s(j['comparison_from']) != null && _s(j['comparison_to']) != null
            ? 'vs ${_s(j['comparison_from'])} – ${_s(j['comparison_to'])}'
            : null,
      );
  final String periodLabel;
  final String currency;
  final String confidence;
  final GraphSeries series;
  final ReportSummary summary;
  final ReportStory story;
  final List<TimelineEvent> timelineEvents;
  final PeriodDelta? delta;
  final String? comparisonLabel;
}

class DrilldownItem {
  const DrilldownItem({required this.label, this.amount, this.currency, this.when, this.subtitle});
  factory DrilldownItem.fromJson(Map<String, dynamic> j) => DrilldownItem(
        label: _s(j['label']) ?? '',
        amount: _s(j['amount']),
        currency: _s(j['currency']),
        when: _s(j['when']),
        subtitle: _s(j['subtitle']),
      );
  final String label;
  final String? amount;
  final String? currency;
  final String? when;
  final String? subtitle;
}

class DrilldownResult {
  const DrilldownResult({required this.title, required this.currency, required this.items, required this.explanation, this.total});
  factory DrilldownResult.fromJson(Map<String, dynamic> j) => DrilldownResult(
        title: _s(j['title']) ?? '',
        currency: _s(j['currency']) ?? 'INR',
        total: _s(j['total']),
        explanation: _s(j['explanation']) ?? '',
        items: ((j['items'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => DrilldownItem.fromJson(e.cast<String, dynamic>()))
            .toList(),
      );
  final String title;
  final String currency;
  final String? total;
  final String explanation;
  final List<DrilldownItem> items;
}

/// The session blob echoed back to the server (stateless conversation memory).
class ChatContext {
  const ChatContext(this.raw);
  factory ChatContext.fromJson(Map<String, dynamic> j) => ChatContext(j);
  final Map<String, dynamic> raw;
  Map<String, dynamic> toJson() => raw;
}

class EvidenceItem {
  const EvidenceItem({required this.label, this.value, this.when});
  factory EvidenceItem.fromJson(Map<String, dynamic> j) =>
      EvidenceItem(label: _s(j['label']) ?? '', value: _s(j['value']), when: _s(j['when']));
  final String label;
  final String? value;
  final String? when;
}

class Explanation {
  const Explanation({
    required this.claim,
    required this.confidence,
    required this.reasoning,
    required this.evidence,
    this.confidenceWord,
    this.whyItMatters,
  });
  factory Explanation.fromJson(Map<String, dynamic> j) => Explanation(
        claim: _s(j['claim']) ?? '',
        confidence: _s(j['confidence']) ?? 'low',
        confidenceWord: _s(j['confidence_word']),
        reasoning: _s(j['reasoning']) ?? '',
        whyItMatters: _s(j['why_it_matters']),
        evidence: ((j['evidence'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => EvidenceItem.fromJson(e.cast<String, dynamic>()))
            .toList(),
      );
  final String claim;
  final String confidence;
  final String? confidenceWord;
  final String reasoning;
  final String? whyItMatters;
  final List<EvidenceItem> evidence;
}

// --- Forecasting (4b-4) ------------------------------------------------------

List<T> _list<T>(dynamic v, T Function(Map<String, dynamic>) f) =>
    ((v as List?) ?? const []).whereType<Map>().map((e) => f(e.cast<String, dynamic>())).toList();

class ScenarioPath {
  const ScenarioPath({required this.mode, required this.label, this.eta, required this.monthlyRate, required this.narrative});
  factory ScenarioPath.fromJson(Map<String, dynamic> j) => ScenarioPath(
        mode: _s(j['mode']) ?? '',
        label: _s(j['label']) ?? '',
        eta: _s(j['eta']),
        monthlyRate: _s(j['monthly_rate']) ?? '0',
        narrative: _s(j['narrative']) ?? '',
      );
  final String mode;
  final String label;
  final String? eta;
  final String monthlyRate;
  final String narrative;
}

class OpportunityCost {
  const OpportunityCost({required this.leverLabel, this.annualSavings, this.daysEarlier, required this.summary});
  factory OpportunityCost.fromJson(Map<String, dynamic> j) => OpportunityCost(
        leverLabel: _s(j['lever_label']) ?? '',
        annualSavings: _s(j['annual_savings']),
        daysEarlier: (j['days_earlier'] as num?)?.toInt(),
        summary: _s(j['summary']) ?? '',
      );
  final String leverLabel;
  final String? annualSavings;
  final int? daysEarlier;
  final String summary;
}

class ForecastStory {
  const ForecastStory({required this.beginning, required this.middle, required this.end});
  factory ForecastStory.fromJson(Map<String, dynamic> j) => ForecastStory(
        beginning: _s(j['beginning']) ?? '', middle: _s(j['middle']) ?? '', end: _s(j['end']) ?? '');
  final String beginning;
  final String middle;
  final String end;
}

class LeverChip {
  const LeverChip({required this.label, required this.ref});
  factory LeverChip.fromJson(Map<String, dynamic> j) =>
      LeverChip(label: _s(j['label']) ?? '', ref: _s(j['ref']) ?? '');
  final String label;
  final String ref;
}

class TimelineCandidate {
  const TimelineCandidate({required this.label, this.date, required this.kind});
  factory TimelineCandidate.fromJson(Map<String, dynamic> j) =>
      TimelineCandidate(label: _s(j['label']) ?? '', date: _s(j['date']), kind: _s(j['kind']) ?? 'forecast');
  final String label;
  final String? date;
  final String kind;
}

class GoalRef {
  const GoalRef({required this.id, required this.name, this.eta, this.progressPct});
  factory GoalRef.fromJson(Map<String, dynamic> j) => GoalRef(
        id: _s(j['id']) ?? '', name: _s(j['name']) ?? '', eta: _s(j['eta']),
        progressPct: (j['progress_pct'] as num?)?.toDouble());
  final String id;
  final String name;
  final String? eta;
  final double? progressPct;
}

class FutureMe {
  const FutureMe({this.currentPath, this.optimisticPath, this.conservativePath});
  static ScenarioPath? _p(dynamic v) => v is Map ? ScenarioPath.fromJson(v.cast<String, dynamic>()) : null;
  factory FutureMe.fromJson(Map<String, dynamic> j) => FutureMe(
        currentPath: _p(j['current_path']), optimisticPath: _p(j['optimistic_path']),
        conservativePath: _p(j['conservative_path']));
  final ScenarioPath? currentPath;
  final ScenarioPath? optimisticPath;
  final ScenarioPath? conservativePath;
}

class Forecast {
  const Forecast({
    required this.kind,
    required this.headline,
    required this.currency,
    required this.confidence,
    this.confidenceWord,
    this.confidenceNote,
    required this.reasoning,
    this.scenarios = const [],
    this.evidence = const [],
    this.opportunityCosts = const [],
    this.story,
    this.levers = const [],
    this.appliedLevers = const [],
    this.timelineCandidates = const [],
    this.goals = const [],
    this.futureMe,
    this.followUps = const [],
    this.surfacedLesson,
    this.accuracyNote,
    this.explainRef,
  });
  factory Forecast.fromJson(Map<String, dynamic> j) => Forecast(
        kind: _s(j['kind']) ?? 'goal',
        headline: _s(j['headline']) ?? '',
        currency: _s(j['currency']) ?? 'INR',
        confidence: _s(j['confidence']) ?? 'low',
        confidenceWord: _s(j['confidence_word']),
        confidenceNote: _s(j['confidence_note']),
        reasoning: _s(j['reasoning']) ?? '',
        scenarios: _list(j['scenarios'], ScenarioPath.fromJson),
        evidence: _list(j['evidence'], EvidenceItem.fromJson),
        opportunityCosts: _list(j['opportunity_costs'], OpportunityCost.fromJson),
        story: j['story'] is Map ? ForecastStory.fromJson((j['story'] as Map).cast<String, dynamic>()) : null,
        levers: _list(j['levers'], LeverChip.fromJson),
        appliedLevers: _list(j['applied_levers'], LeverChip.fromJson),
        timelineCandidates: _list(j['timeline_candidates'], TimelineCandidate.fromJson),
        goals: _list(j['goals'], GoalRef.fromJson),
        futureMe: j['future_me'] is Map ? FutureMe.fromJson((j['future_me'] as Map).cast<String, dynamic>()) : null,
        followUps: _list(j['follow_ups'], ChatOption.fromJson),
        surfacedLesson: _s(j['surfaced_lesson']),
        accuracyNote: _s(j['accuracy_note']),
        explainRef: _s(j['explain_ref']),
      );
  final String kind;
  final String headline;
  final String currency;
  final String confidence;
  final String? confidenceWord;
  final String? confidenceNote;
  final String reasoning;
  final List<ScenarioPath> scenarios;
  final List<EvidenceItem> evidence;
  final List<OpportunityCost> opportunityCosts;
  final ForecastStory? story;
  final List<LeverChip> levers;
  final List<LeverChip> appliedLevers;
  final List<TimelineCandidate> timelineCandidates;
  final List<GoalRef> goals;
  final FutureMe? futureMe;
  final List<ChatOption> followUps;
  final String? surfacedLesson;
  final String? accuracyNote;
  final String? explainRef;
}

// --- Learning loop (4b-5a) ---------------------------------------------------

class FollowUpOption {
  const FollowUpOption({required this.label, required this.value});
  factory FollowUpOption.fromJson(Map<String, dynamic> j) =>
      FollowUpOption(label: _s(j['label']) ?? '', value: _s(j['value']) ?? '');
  final String label;
  final String value;
}

class FollowUpQuestion {
  const FollowUpQuestion({
    required this.id,
    required this.kind,
    required this.importance,
    this.subjectLabel,
    required this.claim,
    required this.question,
    this.options = const [],
  });
  factory FollowUpQuestion.fromJson(Map<String, dynamic> j) => FollowUpQuestion(
        id: _s(j['id']) ?? '',
        kind: _s(j['kind']) ?? '',
        importance: _s(j['importance']) ?? '',
        subjectLabel: _s(j['subject_label']),
        claim: _s(j['claim']) ?? '',
        question: _s(j['question']) ?? '',
        options: _list(j['options'], FollowUpOption.fromJson),
      );
  final String id;
  final String kind;
  final String importance;
  final String? subjectLabel;
  final String claim;
  final String question;
  final List<FollowUpOption> options;
}

class FollowUpAck {
  const FollowUpAck({required this.acknowledged, this.circumstance, this.lessonSuggestion});
  factory FollowUpAck.fromJson(Map<String, dynamic> j) => FollowUpAck(
        acknowledged: _s(j['acknowledged']) ?? '',
        circumstance: _s(j['circumstance']),
        lessonSuggestion: _s(j['lesson_suggestion']),
      );
  final String acknowledged;
  final String? circumstance;
  final String? lessonSuggestion;
}

// --- Companion intelligence (4b-5b) ------------------------------------------

class LifeLesson {
  const LifeLesson({
    required this.id, required this.lesson, required this.category, required this.confidence,
    required this.status, required this.occurrences, this.timesHelpful = 0,
  });
  factory LifeLesson.fromJson(Map<String, dynamic> j) => LifeLesson(
        id: _s(j['id']) ?? '', lesson: _s(j['lesson']) ?? '', category: _s(j['category']) ?? '',
        confidence: _s(j['confidence']) ?? 'low', status: _s(j['status']) ?? 'active',
        occurrences: (j['occurrences'] as num?)?.toInt() ?? 1,
        timesHelpful: (j['times_helpful'] as num?)?.toInt() ?? 0,
      );
  final String id;
  final String lesson;
  final String category;
  final String confidence;
  final String status;
  final int occurrences;
  final int timesHelpful;
}

class ReflectionPrompt {
  const ReflectionPrompt({required this.trigger, required this.importance, required this.question, this.options = const []});
  factory ReflectionPrompt.fromJson(Map<String, dynamic> j) => ReflectionPrompt(
        trigger: _s(j['trigger']) ?? '', importance: _s(j['importance']) ?? '',
        question: _s(j['question']) ?? '', options: _list(j['options'], FollowUpOption.fromJson),
      );
  final String trigger;
  final String importance;
  final String question;
  final List<FollowUpOption> options;
}

class FinancialIdentity {
  const FinancialIdentity({this.focusAreas = const [], this.strongestHabit, this.currentChallenge, required this.currency});
  factory FinancialIdentity.fromJson(Map<String, dynamic> j) => FinancialIdentity(
        focusAreas: ((j['focus_areas'] as List?) ?? const []).map((e) => e.toString()).toList(),
        strongestHabit: _s(j['strongest_habit']), currentChallenge: _s(j['current_challenge']),
        currency: _s(j['currency']) ?? 'INR',
      );
  final List<String> focusAreas;
  final String? strongestHabit;
  final String? currentChallenge;
  final String currency;
}

class RecapAchievement {
  const RecapAchievement({required this.type, required this.importance, required this.label});
  factory RecapAchievement.fromJson(Map<String, dynamic> j) => RecapAchievement(
        type: _s(j['type']) ?? '', importance: _s(j['importance']) ?? '', label: _s(j['label']) ?? '');
  final String type;
  final String importance;
  final String label;
}

class CompanionRecap {
  const CompanionRecap({
    required this.financialIdentity, this.goals = const [], this.habits = const [],
    this.lessons = const [], this.achievements = const [],
  });
  factory CompanionRecap.fromJson(Map<String, dynamic> j) => CompanionRecap(
        financialIdentity: FinancialIdentity.fromJson((j['financial_identity'] as Map).cast<String, dynamic>()),
        goals: ((j['goals'] as List?) ?? const []).whereType<Map>().map((e) => _s(e['name']) ?? '').toList(),
        habits: ((j['habits'] as List?) ?? const []).map((e) => e.toString()).toList(),
        lessons: _list(j['lessons'], LifeLesson.fromJson),
        achievements: _list(j['achievements'], RecapAchievement.fromJson),
      );
  final FinancialIdentity financialIdentity;
  final List<String> goals;
  final List<String> habits;
  final List<LifeLesson> lessons;
  final List<RecapAchievement> achievements;
}

class ChatTurn {
  const ChatTurn({
    required this.type,
    this.message,
    this.route,
    this.options = const [],
    this.report,
    this.drilldown,
    this.forecast,
    this.followUp,
    this.reflection,
    this.recap,
    this.explainRef,
    this.confidence,
    this.followUps = const [],
    this.session,
  });
  factory ChatTurn.fromJson(Map<String, dynamic> j) => ChatTurn(
        type: _s(j['type']) ?? 'answer',
        message: _s(j['message']),
        route: _s(j['route']),
        options: ((j['options'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => ChatOption.fromJson(e.cast<String, dynamic>()))
            .toList(),
        report: j['report'] is Map ? ReportSession.fromJson((j['report'] as Map).cast<String, dynamic>()) : null,
        drilldown: j['drilldown'] is Map ? DrilldownResult.fromJson((j['drilldown'] as Map).cast<String, dynamic>()) : null,
        forecast: j['forecast'] is Map ? Forecast.fromJson((j['forecast'] as Map).cast<String, dynamic>()) : null,
        followUp: j['follow_up'] is Map ? FollowUpQuestion.fromJson((j['follow_up'] as Map).cast<String, dynamic>()) : null,
        reflection: j['reflection'] is Map ? ReflectionPrompt.fromJson((j['reflection'] as Map).cast<String, dynamic>()) : null,
        recap: j['recap'] is Map ? CompanionRecap.fromJson((j['recap'] as Map).cast<String, dynamic>()) : null,
        explainRef: _s(j['explain_ref']),
        confidence: _s(j['confidence']),
        followUps: ((j['follow_ups'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => ChatOption.fromJson(e.cast<String, dynamic>()))
            .toList(),
        session: j['session'] is Map ? ChatContext.fromJson((j['session'] as Map).cast<String, dynamic>()) : null,
      );
  final String type;
  final String? message;
  final String? route;          // how-to / tour: a screen the client can offer to open
  final List<ChatOption> options;
  final ReportSession? report;
  final DrilldownResult? drilldown;
  final Forecast? forecast;
  final FollowUpQuestion? followUp;
  final ReflectionPrompt? reflection;
  final CompanionRecap? recap;
  final String? explainRef;
  final String? confidence;
  final List<ChatOption> followUps;
  final ChatContext? session;
}
