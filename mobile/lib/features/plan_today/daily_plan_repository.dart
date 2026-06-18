import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../core/format/dates.dart';

/// Writes a day's budget / overspend reason. Reads go through the calendar
/// day-detail provider (which already has budget, spent, remaining).
class DailyPlanRepository {
  DailyPlanRepository(this._dio);
  final Dio _dio;

  /// Set/adjust the day's budget. Throws (ValidationError) if locked and
  /// [override] is false — the caller then re-confirms with override: true.
  Future<void> setBudget(DateTime date, String amount, {bool override = false}) =>
      _put(date, {'planned_budget': amount, 'override': override});

  Future<void> setOverspendReason(DateTime date, String reason) =>
      _put(date, {'overspend_reason': reason});

  Future<void> _put(DateTime date, Map<String, dynamic> body) async {
    try {
      await _dio.put<dynamic>('/daily-plans/${ymd(date)}', data: body);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final dailyPlanRepositoryProvider =
    Provider<DailyPlanRepository>((ref) => DailyPlanRepository(ref.watch(dioProvider)));
