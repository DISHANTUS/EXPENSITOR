import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';

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
  const Festivals({required this.ready, this.currency = 'INR', this.upcoming = const []});

  factory Festivals.fromJson(Map<String, dynamic> j) => Festivals(
        ready: j['ready'] == true,
        currency: (j['currency'] ?? 'INR').toString(),
        upcoming: [
          for (final f in (j['upcoming'] as List? ?? const []))
            UpcomingFestival.fromJson(Map<String, dynamic>.from(f as Map)),
        ],
      );

  /// False when the baked festival calendar has run out of years. The app then
  /// says nothing rather than guessing a lunar date.
  final bool ready;
  final String currency;
  final List<UpcomingFestival> upcoming;
}

class FestivalRepository {
  FestivalRepository(this._dio);
  final Dio _dio;

  Future<Festivals> upcoming() async {
    try {
      final res = await _dio.get<dynamic>('/festivals', queryParameters: {'limit': 3});
      return Festivals.fromJson(Map<String, dynamic>.from(res.data as Map));
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final festivalRepositoryProvider =
    Provider<FestivalRepository>((ref) => FestivalRepository(ref.watch(dioProvider)));

final festivalsProvider =
    FutureProvider.autoDispose<Festivals>((ref) => ref.watch(festivalRepositoryProvider).upcoming());
