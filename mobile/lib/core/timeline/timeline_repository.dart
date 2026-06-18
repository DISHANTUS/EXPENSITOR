import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import 'timeline_models.dart';

class TimelineRepository {
  TimelineRepository(this._dio);
  final Dio _dio;

  Future<Timeline> getTimeline() async {
    try {
      final res = await _dio.get<dynamic>('/timeline');
      return Timeline.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Add a user life event (a non-finance milestone) to the timeline.
  Future<void> addLifeEvent({required String title, required String date, String kind = 'milestone', String? icon}) async {
    try {
      await _dio.post<dynamic>('/life-events', data: {
        'title': title, 'event_date': date, 'kind': kind, if (icon != null) 'icon': icon,
      });
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Deterministic memory search ("everything involving Ravi", "June 2026", …).
  Future<TimelineSearchResult> search(String q) async {
    try {
      final res = await _dio.get<dynamic>('/timeline/search', queryParameters: {'q': q});
      return TimelineSearchResult.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final timelineRepositoryProvider =
    Provider<TimelineRepository>((ref) => TimelineRepository(ref.watch(dioProvider)));

/// The user's life timeline. Auto-disposes; the screen refreshes it on entry.
final timelineProvider =
    FutureProvider.autoDispose<Timeline>((ref) => ref.watch(timelineRepositoryProvider).getTimeline());

/// Memory search results for a query (family).
final timelineSearchProvider = FutureProvider.autoDispose
    .family<TimelineSearchResult, String>((ref, q) => ref.watch(timelineRepositoryProvider).search(q));
