import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/cache/offline_cache.dart';

/// A festival coming up, and what it cost this user last time.
///
/// `line` is written by the backend, not assembled here: the honest wording
/// depends on things only the server knows (is there history, was it actually a
/// spike, is the date moon-dependent). Restating those numbers in the UI is how
/// two surfaces drift apart and start contradicting each other.
class UpcomingFestival {
  const UpcomingFestival({
    required this.name,
    required this.date,
    required this.daysAway,
    required this.line,
    this.approximate = false,
    this.extra,
  });

  factory UpcomingFestival.fromJson(Map<String, dynamic> j) {
    final last = j['last_time'] as Map?;
    final notable = last?['notable'] == true;
    return UpcomingFestival(
      name: (j['name'] ?? '').toString(),
      date: (j['date'] ?? '').toString(),
      daysAway: (j['days_away'] as num?)?.toInt() ?? 0,
      approximate: j['approximate'] == true,
      line: (j['line'] ?? '').toString(),
      // Only carried when it was genuinely a spike — otherwise there's no
      // number worth putting on screen.
      extra: notable ? double.tryParse(last!['extra'].toString()) : null,
    );
  }

  final String name;
  final String date;
  final int daysAway;
  final bool approximate;
  final String line;

  /// What this festival cost OVER a normal stretch last time, measured from the
  /// user's own ledger. Null when there's no history or it wasn't a spike.
  final double? extra;
}

class Festivals {
  const Festivals({required this.ready, this.currency = 'INR', this.regions = const [], this.upcoming = const []});

  factory Festivals.fromJson(Map<String, dynamic> j) => Festivals(
        ready: j['ready'] == true,
        currency: (j['currency'] ?? 'INR').toString(),
        regions: [for (final r in (j['regions'] as List? ?? const [])) r.toString()],
        upcoming: [
          for (final f in (j['upcoming'] as List? ?? const []))
            UpcomingFestival.fromJson(Map<String, dynamic>.from(f as Map)),
        ],
      );

  /// False when the baked festival calendar has run out of years. The app then
  /// says nothing rather than guessing a lunar date.
  final bool ready;
  final String currency;

  /// Which calendars this user is being shown (IN, JP, or both). Empty when
  /// none covers them — in which case `ready` is false and there's nothing to
  /// show, which beats showing someone else's festivals.
  final List<String> regions;

  final List<UpcomingFestival> upcoming;
}

class FestivalRepository {
  FestivalRepository(this._dio, this._cache);
  final Dio _dio;
  final OfflineCache _cache;

  /// Goes through the offline cache, so the last answer stays on the phone and
  /// still shows with no internet.
  ///
  /// Festivals are the ideal thing to cache: the dates are fixed months ahead,
  /// so yesterday's copy is exactly as true as today's. The measured "last time
  /// this cost you X" can go stale by a day's spending, which is a rounding
  /// error against a number describing a fortnight last year.
  Future<Festivals> upcoming() async => Festivals.fromJson(
        await _cache.fetchJson(_dio, '/festivals', query: {
          'limit': 3,
          // The phone's UTC offset — the "you've moved country" signal, free.
          // Land in Tokyo and this becomes 540 on its own: no permission, no
          // prompt, no battery, and it still works offline. GPS would cost all
          // of those to answer the same single question. An explicit setting
          // overrides it server-side anyway.
          'utc_offset_minutes': DateTime.now().timeZoneOffset.inMinutes,
        }),
      );
}

final festivalRepositoryProvider = Provider<FestivalRepository>(
    (ref) => FestivalRepository(ref.watch(dioProvider), ref.watch(offlineCacheProvider)));

final festivalsProvider =
    FutureProvider.autoDispose<Festivals>((ref) => ref.watch(festivalRepositoryProvider).upcoming());
