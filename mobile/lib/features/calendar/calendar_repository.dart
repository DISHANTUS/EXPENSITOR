import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../core/format/dates.dart';
import 'calendar_models.dart';

class CalendarRepository {
  CalendarRepository(this._dio);
  final Dio _dio;

  Future<Map<String, CalendarMarkerType>> markerTypes() async {
    try {
      final res = await _dio.get<dynamic>('/calendar/marker-types');
      final list = (res.data as List?) ?? const [];
      final types = list
          .whereType<Map>()
          .map((e) => CalendarMarkerType.fromJson(e.cast<String, dynamic>()));
      return {for (final t in types) t.key: t};
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<MonthView> month(int year, int month) => _get(
        '/calendar/month',
        MonthView.fromJson,
        query: {'year': year, 'month': month},
      );

  Future<DayDetail> day(DateTime date) => _get('/calendar/day/${ymd(date)}', DayDetail.fromJson);

  Future<T> _get<T>(String path, T Function(Map<String, dynamic>) parse, {Map<String, dynamic>? query}) async {
    try {
      final res = await _dio.get<dynamic>(path, queryParameters: query);
      return parse((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final calendarRepositoryProvider =
    Provider<CalendarRepository>((ref) => CalendarRepository(ref.watch(dioProvider)));

/// Cached registry; falls back to the built-in subset if the catalog fetch fails.
final markerRegistryProvider = FutureProvider<Map<String, CalendarMarkerType>>((ref) async {
  try {
    return await ref.watch(calendarRepositoryProvider).markerTypes();
  } on AppError {
    return fallbackMarkers;
  }
});

typedef YearMonth = ({int year, int month});

final monthViewProvider =
    FutureProvider.autoDispose.family<MonthView, YearMonth>((ref, ym) => ref.watch(calendarRepositoryProvider).month(ym.year, ym.month));

/// Keyed by ISO date string (yyyy-MM-dd).
final dayDetailProvider = FutureProvider.autoDispose.family<DayDetail, String>(
    (ref, isoDate) => ref.watch(calendarRepositoryProvider).day(DateTime.parse(isoDate)));
