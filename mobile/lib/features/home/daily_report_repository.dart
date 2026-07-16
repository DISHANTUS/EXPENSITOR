import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';

/// The nearest goal, as the report sees it. The numbers come from the savings
/// engine — the same source the Plan screen reads — so the two can't disagree.
class ReportGoal {
  const ReportGoal({
    required this.id,
    required this.name,
    required this.targetAmount,
    required this.remaining,
    this.daysLeft,
    this.status,
  });

  factory ReportGoal.fromJson(Map<String, dynamic> j) => ReportGoal(
        id: (j['id'] ?? '').toString(),
        name: (j['name'] ?? '').toString(),
        targetAmount: (j['target_amount'] ?? '0').toString(),
        remaining: (j['remaining'] ?? '0').toString(),
        daysLeft: (j['days_left'] as num?)?.toInt(),
        status: j['status'] as String?,
      );

  final String id;
  final String name;
  final String targetAmount;
  final String remaining;
  final int? daysLeft;
  final String? status;
}

/// How today went. Everything here is derived on read; nothing is stored.
class DailyReport {
  const DailyReport({
    required this.date,
    required this.currency,
    required this.dayDone,
    required this.dailyAllowance,
    required this.spentToday,
    required this.savedToday,
    required this.status,
    required this.streakDays,
    required this.windowDays,
    required this.windowNet,
    this.goal,
    this.lines = const [],
  });

  factory DailyReport.fromJson(Map<String, dynamic> j) => DailyReport(
        date: (j['date'] ?? '').toString(),
        currency: (j['currency'] ?? 'INR').toString(),
        dayDone: j['day_done'] == true,
        dailyAllowance: (j['daily_allowance'] ?? '0').toString(),
        spentToday: (j['spent_today'] ?? '0').toString(),
        savedToday: (j['saved_today'] ?? '0').toString(),
        status: (j['status'] ?? 'even').toString(),
        streakDays: (j['streak_days'] as num?)?.toInt() ?? 0,
        windowDays: (j['window_days'] as num?)?.toInt() ?? 0,
        windowNet: (j['window_net'] ?? '0').toString(),
        goal: j['goal'] == null ? null : ReportGoal.fromJson(Map<String, dynamic>.from(j['goal'] as Map)),
        lines: [for (final l in (j['lines'] as List? ?? const [])) l.toString()],
      );

  final String date;
  final String currency;

  /// False while the day is still in progress — the wording stays provisional
  /// and nothing gets called a finished result.
  final bool dayDone;

  final String dailyAllowance;
  final String spentToday;
  final String savedToday; // negative means over the allowance
  final String status; // under | over | even
  final int streakDays;
  final int windowDays;
  final String windowNet;
  final ReportGoal? goal;
  final List<String> lines;

  double get savedTodayValue => double.tryParse(savedToday) ?? 0;
  bool get hasBudget => (double.tryParse(dailyAllowance) ?? 0) > 0;
}

class DailyReportRepository {
  DailyReportRepository(this._dio);
  final Dio _dio;

  Future<DailyReport> get() async {
    try {
      final res = await _dio.get<dynamic>(
        '/daily-report',
        // The device's local hour, same convention as the greeting: only the
        // phone knows whether THIS user's day is actually over.
        queryParameters: {'hour': DateTime.now().hour},
      );
      return DailyReport.fromJson(Map<String, dynamic>.from(res.data as Map));
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final dailyReportRepositoryProvider =
    Provider<DailyReportRepository>((ref) => DailyReportRepository(ref.watch(dioProvider)));

final dailyReportProvider =
    FutureProvider.autoDispose<DailyReport>((ref) => ref.watch(dailyReportRepositoryProvider).get());
