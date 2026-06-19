import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../core/format/dates.dart';

String? _s(dynamic v) => v?.toString();

/// A borrowed debt the user owes (read view).
class PayableSummary {
  const PayableSummary({
    required this.id,
    required this.who,
    required this.amount,
    required this.currency,
    required this.returnExpectation,
    this.dueDate,
  });

  factory PayableSummary.fromJson(Map<String, dynamic> j) => PayableSummary(
        id: _s(j['id']) ?? '',
        who: _s(j['source_name']) ?? 'someone',
        amount: _s(j['converted_amount']) ?? '0',
        currency: _s(j['base_currency']) ?? 'INR',
        returnExpectation: _s(j['return_expectation']) ?? 'required',
        dueDate: j['due_date'] != null ? DateTime.tryParse(j['due_date'].toString()) : null,
      );

  final String id;
  final String who;
  final String amount;
  final String currency;
  final String returnExpectation;
  final DateTime? dueDate;
}

class RepaymentAlt {
  const RepaymentAlt({this.date, required this.label});
  factory RepaymentAlt.fromJson(Map<String, dynamic> j) => RepaymentAlt(
        date: j['date'] != null ? DateTime.tryParse(j['date'].toString()) : null,
        label: _s(j['label']) ?? '',
      );
  final DateTime? date; // null = a non-date suggestion (e.g. "trim spending")
  final String label;
}

/// Advary's repayment plan — the affordability verdict made human.
class RepaymentPlan {
  const RepaymentPlan({
    required this.feasible,
    required this.verdict,
    required this.headline,
    required this.monthlyPace,
    required this.impact,
    required this.alternatives,
  });

  factory RepaymentPlan.fromJson(Map<String, dynamic> j) => RepaymentPlan(
        feasible: j['feasible'] == true,
        verdict: _s(j['verdict']) ?? '',
        headline: _s(j['headline']) ?? '',
        monthlyPace: _s(j['monthly_pace']) ?? '',
        impact: ((j['impact'] as List?) ?? const []).map((e) => e.toString()).toList(),
        alternatives: ((j['alternatives'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => RepaymentAlt.fromJson(e.cast<String, dynamic>()))
            .toList(),
      );

  final bool feasible;
  final String verdict;
  final String headline;
  final String monthlyPace;
  final List<String> impact;
  final List<RepaymentAlt> alternatives;
}

class PayableRepository {
  PayableRepository(this._dio);
  final Dio _dio;

  Future<PayableSummary> get(String id) async {
    try {
      final r = await _dio.get<dynamic>('/payables/$id');
      return PayableSummary.fromJson((r.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<RepaymentPlan> repaymentPlan(String id, {required DateTime targetDate, required String preference}) async {
    try {
      final r = await _dio.post<dynamic>('/payables/$id/repayment-plan',
          data: {'target_date': ymd(targetDate), 'preference': preference});
      return RepaymentPlan.fromJson((r.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Accept a plan → records a repayment commitment (Advary follows up later).
  Future<void> commitRepayment(String id, {required DateTime targetDate, required String preference}) async {
    try {
      await _dio.post<dynamic>('/payables/$id/commit-repayment',
          data: {'target_date': ymd(targetDate), 'preference': preference});
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final payableRepositoryProvider = Provider<PayableRepository>((ref) => PayableRepository(ref.watch(dioProvider)));

final payableSummaryProvider =
    FutureProvider.autoDispose.family<PayableSummary, String>((ref, id) => ref.watch(payableRepositoryProvider).get(id));
