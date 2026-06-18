import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import 'mood_models.dart';

class MoodRepository {
  MoodRepository(this._dio);
  final Dio _dio;

  /// Records an achievement as a timeline candidate (Sprint 6 consumes these).
  Future<void> recordTimelineCandidate(String label) async {
    try {
      await _dio.post<dynamic>('/companion/events', data: {
        'event_type': 'system', 'surface': 'companion', 'action': 'timeline_candidate',
        'payload': {'label': label, 'kind': 'achievement'},
      });
    } on DioException catch (_) {/* best-effort hook; never blocks the reaction */}
  }

  Future<MoodState> getMood() async {
    try {
      // Send the device's local hour so the greeting's time-of-day matches what
      // the user actually sees (not the server's UTC clock).
      final res = await _dio.get<dynamic>('/companion/mood',
          queryParameters: {'hour': DateTime.now().hour});
      return MoodState.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final moodRepositoryProvider = Provider<MoodRepository>((ref) => MoodRepository(ref.watch(dioProvider)));

/// The companion's current mood. Auto-disposes; screens refresh it on entry.
final companionMoodProvider = FutureProvider.autoDispose<MoodState>((ref) {
  return ref.watch(moodRepositoryProvider).getMood();
});
