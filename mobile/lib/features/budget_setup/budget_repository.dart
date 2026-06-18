import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../core/format/dates.dart';

/// Derived budget from GET /budget/summary.
class BudgetSummary {
  const BudgetSummary({
    required this.currency,
    required this.monthlyIncome,
    required this.monthlyCommitments,
    required this.monthlyGoals,
    required this.monthlyDiscretionary,
    required this.weekly,
    required this.daily,
  });

  factory BudgetSummary.fromJson(Map<String, dynamic> j) => BudgetSummary(
        currency: (j['base_currency'] ?? 'INR').toString(),
        monthlyIncome: (j['monthly_income'] ?? '0').toString(),
        monthlyCommitments: (j['monthly_commitments'] ?? '0').toString(),
        monthlyGoals: (j['monthly_goal_contributions'] ?? '0').toString(),
        monthlyDiscretionary: (j['monthly_discretionary'] ?? '0').toString(),
        weekly: (j['weekly_budget'] ?? '0').toString(),
        daily: (j['daily_budget'] ?? '0').toString(),
      );

  final String currency;
  final String monthlyIncome;
  final String monthlyCommitments;
  final String monthlyGoals;
  final String monthlyDiscretionary;
  final String weekly;
  final String daily;
}

/// Writes the profile entities the Budget Setup interview collects, plus the
/// lent-money flow (Person + receivable). Reuses 4a-1 backend endpoints.
class BudgetRepository {
  BudgetRepository(this._dio);
  final Dio _dio;

  Future<String> createPerson({required String name, required String relationshipType, String? reason}) async {
    final res = await _post('/persons', {
      'name': name,
      'relationship_type': relationshipType,
      if (reason != null && reason.trim().isNotEmpty) 'ai_metadata': {'why': reason.trim()},
    });
    return (res['id']).toString();
  }

  Future<void> createIncomeSource({
    required String label,
    required String sourceType,
    required String amount,
    required String currency,
    int recurrenceDay = 1,
    String? reason,
  }) =>
      _post('/income-sources', {
        'label': label,
        'source_type': sourceType,
        'kind': 'recurring',
        'original_amount': amount,
        'original_currency': currency.toUpperCase(),
        'recurrence_day': recurrenceDay,
        if (reason != null && reason.trim().isNotEmpty) 'reason': reason.trim(),
        if (reason != null && reason.trim().isNotEmpty) 'ai_metadata': {'why': reason.trim()},
      }).then((_) {});

  Future<void> createRecurringRule({
    required String ruleType,
    required String label,
    required String amount,
    required String currency,
    required int recurrenceDay,
    required DateTime startDate,
    String? reason,
  }) =>
      _post('/recurring-rules', {
        'rule_type': ruleType,
        'label': label,
        'original_amount': amount,
        'original_currency': currency.toUpperCase(),
        'recurrence_day': recurrenceDay,
        'start_date': ymd(startDate),
        if (reason != null && reason.trim().isNotEmpty) 'reason': reason.trim(),
        if (reason != null && reason.trim().isNotEmpty) 'ai_metadata': {'why': reason.trim()},
      }).then((_) {});

  Future<void> createSavingsGoal({
    required String name,
    required String amount,
    required String currency,
    String kind = 'monthly_target',
    DateTime? targetDate,
    String? reason,
  }) =>
      _post('/savings-goals', {
        'name': name,
        'kind': kind,
        'original_amount': amount,
        'original_currency': currency.toUpperCase(),
        if (targetDate != null) 'target_date': ymd(targetDate),
        if (reason != null && reason.trim().isNotEmpty) 'reason': reason.trim(),
        if (reason != null && reason.trim().isNotEmpty) 'ai_metadata': {'why': reason.trim()},
      }).then((_) {});

  Future<void> createLentMoney({
    required String personName,
    required String amount,
    required String currency,
    required DateTime expectedReturn,
    String? reason,
    Map<String, dynamic>? aiMetadata,
  }) async {
    final personId = await createPerson(name: personName, relationshipType: 'friend', reason: reason);
    await _post('/receivables', {
      'title': 'Lent to $personName',
      'source_name': personName,
      'source_type': 'friend',
      'kind': 'one_time',
      'original_amount': amount,
      'original_currency': currency.toUpperCase(),
      'expected_date': ymd(expectedReturn),
      'person_id': personId,
      if (reason != null && reason.trim().isNotEmpty) 'notes': reason.trim(),
      if (aiMetadata != null) 'ai_metadata': aiMetadata,
    });
  }

  Future<BudgetSummary> summary() async {
    try {
      final res = await _dio.get<dynamic>('/budget/summary');
      return BudgetSummary.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<BudgetSummary> apply() async {
    try {
      final res = await _dio.post<dynamic>('/budget/apply');
      return BudgetSummary.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body) async {
    try {
      final res = await _dio.post<dynamic>(path, data: body);
      return (res.data is Map) ? (res.data as Map).cast<String, dynamic>() : <String, dynamic>{};
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final budgetRepositoryProvider =
    Provider<BudgetRepository>((ref) => BudgetRepository(ref.watch(dioProvider)));
