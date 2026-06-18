import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';

/// One step of the first-launch guided tour. `route` is the screen the overlay
/// navigates to while the companion narrates `narration` (spoken via `spokenText`).
class TourStep {
  const TourStep({
    required this.key,
    required this.route,
    required this.icon,
    required this.title,
    required this.narration,
    required this.spokenText,
  });

  factory TourStep.fromJson(Map<String, dynamic> j) => TourStep(
        key: (j['key'] ?? '').toString(),
        route: (j['route'] ?? '/home').toString(),
        icon: (j['icon'] ?? '✨').toString(),
        title: (j['title'] ?? '').toString(),
        narration: (j['narration'] ?? '').toString(),
        spokenText: (j['spoken_text'] ?? j['narration'] ?? '').toString(),
      );

  final String key;
  final String route;
  final String icon;
  final String title;
  final String narration;
  final String spokenText;
}

class Tour {
  const Tour({required this.companionName, required this.steps});

  factory Tour.fromJson(Map<String, dynamic> j) => Tour(
        companionName: (j['companion_name'] ?? 'Advary').toString(),
        steps: ((j['steps'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => TourStep.fromJson(e.cast<String, dynamic>()))
            .toList(),
      );

  final String companionName;
  final List<TourStep> steps;
}

class TourRepository {
  TourRepository(this._dio);
  final Dio _dio;

  Future<Tour> fetch() async {
    try {
      final res = await _dio.get<dynamic>('/companion/tour');
      return Tour.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Best-effort: stamp the tour as seen. Never throws (a failed POST shouldn't
  /// trap the user in the overlay).
  Future<void> markComplete() async {
    try {
      await _dio.post<dynamic>('/companion/tour/complete');
    } on DioException {
      // ignore — the local flag already dismissed the overlay.
    }
  }
}

final tourRepositoryProvider =
    Provider<TourRepository>((ref) => TourRepository(ref.watch(dioProvider)));
