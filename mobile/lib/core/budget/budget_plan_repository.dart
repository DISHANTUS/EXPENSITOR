import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';

double _d(dynamic v) => double.tryParse('${v ?? 0}') ?? 0;
String _s(dynamic v) => '${v ?? ''}';

// --- Feasibility (Phase 3) ---------------------------------------------------

class WaterfallStep {
  WaterfallStep(this.label, this.amount, this.remaining);
  final String label;
  final double amount;
  final double remaining;
}

class GoalFeasibility {
  GoalFeasibility(this.goal, this.target, this.band, this.score, this.reason);
  final String goal;
  final double target;
  final String band;   // very_high..very_low
  final int score;
  final String reason;
}

class StructuralFlag {
  StructuralFlag(this.kind, this.severity, this.message);
  final String kind;
  final String severity;  // ok | elevated | high
  final String message;
}

class Feasibility {
  Feasibility({
    required this.currency,
    required this.incomeTotal,
    required this.essentialsTotal,
    required this.buffer,
    required this.comfortable,
    required this.overallBand,
    required this.waterfall,
    required this.goals,
    required this.flags,
    required this.anomalies,
    required this.summary,
  });

  factory Feasibility.fromJson(Map<String, dynamic> j) => Feasibility(
        currency: _s(j['base_currency']),
        incomeTotal: _d(j['income_total']),
        essentialsTotal: _d(j['essentials_total']),
        buffer: _d(j['emergency_buffer']),
        comfortable: _d(j['comfortable_surplus']),
        overallBand: _s(j['overall_band']),
        waterfall: ((j['waterfall'] as List?) ?? const [])
            .map((e) => WaterfallStep(_s(e['label']), _d(e['amount']), _d(e['running_remaining'])))
            .toList(),
        goals: ((j['goals'] as List?) ?? const [])
            .map((e) => GoalFeasibility(_s(e['goal']), _d(e['target_monthly']), _s(e['probability_band']),
                (e['probability_score'] as num?)?.toInt() ?? 0, _s(e['reason'])))
            .toList(),
        flags: ((j['structural_flags'] as List?) ?? const [])
            .map((e) => StructuralFlag(_s(e['kind']), _s(e['severity']), _s(e['message'])))
            .toList(),
        anomalies: ((j['anomalies'] as List?) ?? const []).map((e) => e.toString()).toList(),
        summary: _s(j['summary']),
      );

  final String currency;
  final double incomeTotal;
  final double essentialsTotal;
  final double buffer;
  final double comfortable;
  final String overallBand;
  final List<WaterfallStep> waterfall;
  final List<GoalFeasibility> goals;
  final List<StructuralFlag> flags;
  final List<String> anomalies;
  final String summary;
}

// --- Reality (Phase 2) — income by source + goals, for the profile summary -----

class IncomeLine {
  IncomeLine(this.label, this.sourceType, this.monthly);
  final String label;
  final String sourceType;
  final double monthly;
}

class Reality {
  Reality({required this.currency, required this.incomeSources, required this.incomeTotal, required this.goals});
  factory Reality.fromJson(Map<String, dynamic> j) => Reality(
        currency: _s(j['base_currency']),
        incomeTotal: _d(j['income_total']),
        incomeSources: ((j['income_sources'] as List?) ?? const [])
            .map((e) => IncomeLine(_s(e['label']), _s(e['source_type']), _d(e['monthly']))).toList(),
        goals: (((j['goals'] as Map?)?['lines'] as List?) ?? const []).map((e) => _s(e['label'])).toList(),
      );
  final String currency;
  final List<IncomeLine> incomeSources;
  final double incomeTotal;
  final List<String> goals;
}

// --- Recommendations (Phase 4) -----------------------------------------------

class RecChange {
  RecChange(this.label, this.currentMonthly, this.suggestedMonthly, this.currentDaily,
      this.suggestedDaily, this.impact, this.reason, this.confidence, this.protected);
  final String label;
  final double currentMonthly;
  final double suggestedMonthly;
  final double? currentDaily;
  final double? suggestedDaily;
  final double impact;
  final String reason;
  final String confidence;
  final bool protected;
}

class RecTier {
  RecTier(this.style, this.title, this.totalImpact, this.reaches, this.confidence, this.difficulty, this.changes);
  final String style;
  final String title;
  final double totalImpact;
  final bool reaches;
  final String confidence;
  final String difficulty;
  final List<RecChange> changes;
}

class GrowIncome {
  GrowIncome(this.label, this.detail, this.confidence);
  final String label;
  final String detail;
  final String confidence;
}

class RecommendationSet {
  RecommendationSet({
    required this.currency,
    required this.target,
    required this.gap,
    required this.onTrack,
    required this.tiers,
    required this.growIncome,
    required this.whyNot,
    required this.protectionNote,
    required this.summary,
  });

  factory RecommendationSet.fromJson(Map<String, dynamic> j) => RecommendationSet(
        currency: _s(j['base_currency']),
        target: j['target_monthly'] == null ? null : _d(j['target_monthly']),
        gap: _d(j['gap_monthly']),
        onTrack: j['on_track'] == true,
        tiers: ((j['tiers'] as List?) ?? const []).map((t) => RecTier(
              _s(t['style']), _s(t['title']), _d(t['total_monthly_impact']), t['reaches_goal'] == true,
              _s(t['confidence']), _s(t['difficulty']),
              ((t['changes'] as List?) ?? const []).map((c) => RecChange(
                    _s(c['label']), _d(c['current_monthly']), _d(c['suggested_monthly']),
                    c['current_daily'] == null ? null : _d(c['current_daily']),
                    c['suggested_daily'] == null ? null : _d(c['suggested_daily']),
                    _d(c['monthly_impact']), _s(c['reason']), _s(c['confidence']), c['protected'] == true,
                  )).toList(),
            )).toList(),
        growIncome: ((j['grow_income'] as List?) ?? const [])
            .map((g) => GrowIncome(_s(g['label']), _s(g['detail']), _s(g['confidence']))).toList(),
        whyNot: j['why_not'] == null ? null : _s(j['why_not']),
        protectionNote: j['essential_protection_note'] == null ? null : _s(j['essential_protection_note']),
        summary: _s(j['summary']),
      );

  final String currency;
  final double? target;
  final double gap;
  final bool onTrack;
  final List<RecTier> tiers;
  final List<GrowIncome> growIncome;
  final String? whyNot;
  final String? protectionNote;
  final String summary;
}

class BudgetPlanRepository {
  BudgetPlanRepository(this._dio);
  final Dio _dio;

  Future<Map<String, dynamic>> getProfile() => _get('/users/me/profile');

  Future<void> patchProfile(Map<String, dynamic> body) async {
    try {
      await _dio.patch<dynamic>('/users/me/profile', data: body);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<Reality> reality() async => Reality.fromJson(await _get('/budget/reality'));

  Future<Feasibility> feasibility() async =>
      Feasibility.fromJson(await _get('/budget/feasibility'));

  Future<RecommendationSet> recommendations({double? target}) async =>
      RecommendationSet.fromJson(await _get('/budget/recommendations',
          query: target == null ? null : {'target': target}));

  Future<Map<String, dynamic>> _get(String path, {Map<String, dynamic>? query}) async {
    try {
      final res = await _dio.get<dynamic>(path, queryParameters: query);
      return (res.data as Map).cast<String, dynamic>();
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final budgetPlanRepositoryProvider =
    Provider<BudgetPlanRepository>((ref) => BudgetPlanRepository(ref.watch(dioProvider)));

final profileProvider = FutureProvider.autoDispose<Map<String, dynamic>>(
    (ref) => ref.watch(budgetPlanRepositoryProvider).getProfile());

final realityProvider = FutureProvider.autoDispose<Reality>(
    (ref) => ref.watch(budgetPlanRepositoryProvider).reality());

final feasibilityProvider = FutureProvider.autoDispose<Feasibility>(
    (ref) => ref.watch(budgetPlanRepositoryProvider).feasibility());

final recommendationsProvider = FutureProvider.autoDispose<RecommendationSet>(
    (ref) => ref.watch(budgetPlanRepositoryProvider).recommendations());
