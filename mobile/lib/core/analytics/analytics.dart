import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';

/// A deliberately tiny, fire-and-forget analytics pipe — feeds the developer's
/// GET /dev/stats (intervention open/dismiss rate, commitment acceptance). It
/// must NEVER break a user flow, so every failure is swallowed silently.
class Analytics {
  Analytics(this._dio);
  final Dio _dio;

  void track(String event, [Map<String, dynamic>? props]) {
    _send(event, props); // intentionally not awaited
  }

  Future<void> _send(String event, Map<String, dynamic>? props) async {
    try {
      await _dio.post<dynamic>('/dev/track', data: {'event': event, if (props != null) 'props': props});
    } catch (_) {
      // analytics is best-effort only
    }
  }
}

final analyticsProvider = Provider<Analytics>((ref) => Analytics(ref.watch(dioProvider)));

/// Ids already counted as "shown" this app session (so the orb lighting up once
/// counts once, not on every rebuild).
final shownInterventions = <String>{};
