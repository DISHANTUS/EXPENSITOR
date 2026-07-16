import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/cache/offline_cache.dart';
import 'dashboard_models.dart';

/// Reads the three live advisor endpoints. No mock data. Falls back to the
/// last cached response when offline (see [OfflineCache]).
class DashboardRepository {
  DashboardRepository(this._dio, this._cache);
  final Dio _dio;
  final OfflineCache _cache;

  Future<ProactiveFeed> proactiveFeed() => _get('/advisor/proactive', ProactiveFeed.fromJson);
  Future<DailyBrief> brief() => _get('/advisor/brief', DailyBrief.fromJson);
  Future<HealthSummary> health() => _get('/financial-health', HealthSummary.fromJson);

  Future<T> _get<T>(String path, T Function(Map<String, dynamic>) parse) async =>
      parse(await _cache.fetchJson(_dio, path));
}

final dashboardRepositoryProvider = Provider<DashboardRepository>(
    (ref) => DashboardRepository(ref.watch(dioProvider), ref.watch(offlineCacheProvider)));

// autoDispose: re-fetch fresh each time Home is opened; invalidated on pull-to-refresh.
final proactiveFeedProvider =
    FutureProvider.autoDispose<ProactiveFeed>((ref) => ref.watch(dashboardRepositoryProvider).proactiveFeed());

final dailyBriefProvider =
    FutureProvider.autoDispose<DailyBrief>((ref) => ref.watch(dashboardRepositoryProvider).brief());

final financialHealthProvider =
    FutureProvider.autoDispose<HealthSummary>((ref) => ref.watch(dashboardRepositoryProvider).health());
