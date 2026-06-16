import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import 'dashboard_models.dart';

/// Reads the three live advisor endpoints. No mock data.
class DashboardRepository {
  DashboardRepository(this._dio);
  final Dio _dio;

  Future<ProactiveFeed> proactiveFeed() => _get('/advisor/proactive', ProactiveFeed.fromJson);
  Future<DailyBrief> brief() => _get('/advisor/brief', DailyBrief.fromJson);
  Future<HealthSummary> health() => _get('/financial-health', HealthSummary.fromJson);

  Future<T> _get<T>(String path, T Function(Map<String, dynamic>) parse) async {
    try {
      final res = await _dio.get<dynamic>(path);
      return parse((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final dashboardRepositoryProvider =
    Provider<DashboardRepository>((ref) => DashboardRepository(ref.watch(dioProvider)));

// autoDispose: re-fetch fresh each time Home is opened; invalidated on pull-to-refresh.
final proactiveFeedProvider =
    FutureProvider.autoDispose<ProactiveFeed>((ref) => ref.watch(dashboardRepositoryProvider).proactiveFeed());

final dailyBriefProvider =
    FutureProvider.autoDispose<DailyBrief>((ref) => ref.watch(dashboardRepositoryProvider).brief());

final financialHealthProvider =
    FutureProvider.autoDispose<HealthSummary>((ref) => ref.watch(dashboardRepositoryProvider).health());
