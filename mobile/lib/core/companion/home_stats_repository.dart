import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';

/// The Home Memory Strip — a few already-true numbers that make Home feel personal.
class HomeStats {
  const HomeStats({
    required this.daysWithAdvary,
    required this.goalsCompleted,
    required this.goalsActive,
    required this.relationshipCount,
    required this.totalSaved,
    required this.currency,
    this.strongestHabit,
    this.biggestWin,
  });

  factory HomeStats.fromJson(Map<String, dynamic> j) => HomeStats(
        daysWithAdvary: (j['days_with_advary'] as num?)?.toInt() ?? 1,
        goalsCompleted: (j['goals_completed'] as num?)?.toInt() ?? 0,
        goalsActive: (j['goals_active'] as num?)?.toInt() ?? 0,
        relationshipCount: (j['relationship_count'] as num?)?.toInt() ?? 0,
        totalSaved: double.tryParse('${j['total_saved'] ?? 0}') ?? 0,
        currency: (j['currency'] ?? 'INR').toString(),
        strongestHabit: j['strongest_habit']?.toString(),
        biggestWin: j['biggest_win']?.toString(),
      );

  final int daysWithAdvary;
  final int goalsCompleted;
  final int goalsActive;
  final int relationshipCount;
  final double totalSaved;
  final String currency;
  final String? strongestHabit;
  final String? biggestWin;
}

/// Advary's contextual thought for the Home hero (goal / who-owes / next milestone).
class HomeThought {
  const HomeThought({required this.lines, required this.mood});
  factory HomeThought.fromJson(Map<String, dynamic> j) => HomeThought(
        lines: ((j['lines'] as List?) ?? const []).map((e) => e.toString()).toList(),
        mood: (j['mood'] ?? 'idle').toString(),
      );
  final List<String> lines;
  final String mood;   // idle | celebrating | concerned
}

final homeThoughtProvider = FutureProvider.autoDispose<HomeThought>((ref) async {
  try {
    final res = await ref.watch(dioProvider).get<dynamic>('/companion/home-thought');
    return HomeThought.fromJson((res.data as Map).cast<String, dynamic>());
  } on DioException catch (e) {
    throw mapDioError(e);
  }
});

final homeStatsProvider = FutureProvider.autoDispose<HomeStats>((ref) async {
  try {
    final res = await ref.watch(dioProvider).get<dynamic>('/companion/home-stats');
    return HomeStats.fromJson((res.data as Map).cast<String, dynamic>());
  } on DioException catch (e) {
    throw mapDioError(e);
  }
});

/// A Living Quick Card — a *preview* of one corner of the user's life
/// (their story, their future, their people, today's focus), not a menu button.
class HomeCard {
  const HomeCard({
    required this.key,
    required this.icon,
    required this.title,
    required this.headline,
    required this.route,
    this.subtitle,
  });

  factory HomeCard.fromJson(Map<String, dynamic> j) => HomeCard(
        key: (j['key'] ?? '').toString(),
        icon: (j['icon'] ?? '').toString(),
        title: (j['title'] ?? '').toString(),
        headline: (j['headline'] ?? '').toString(),
        route: (j['route'] ?? '/').toString(),
        subtitle: j['subtitle']?.toString(),
      );

  final String key;
  final String icon;
  final String title;
  final String headline;
  final String route;
  final String? subtitle;
}

final homeCardsProvider = FutureProvider.autoDispose<List<HomeCard>>((ref) async {
  try {
    final res = await ref.watch(dioProvider).get<dynamic>('/companion/home-cards');
    final cards = ((res.data as Map)['cards'] as List?) ?? const [];
    return cards.map((e) => HomeCard.fromJson((e as Map).cast<String, dynamic>())).toList();
  } on DioException catch (e) {
    throw mapDioError(e);
  }
});

/// Advary's warm reaction to a tapped calendar day — the calendar as memory.
class DateReaction {
  const DateReaction({required this.line, required this.mood, required this.emoji});
  factory DateReaction.fromJson(Map<String, dynamic> j) => DateReaction(
        line: (j['line'] ?? '').toString(),
        mood: (j['mood'] ?? 'idle').toString(),
        emoji: (j['emoji'] ?? '✨').toString(),
      );
  final String line;
  final String mood;   // idle | celebrating | concerned
  final String emoji;
}

/// Keyed by `YYYY-MM-DD`. The reaction for a tapped marked date.
final dateReactionProvider =
    FutureProvider.autoDispose.family<DateReaction, String>((ref, ymd) async {
  try {
    final res = await ref
        .watch(dioProvider)
        .get<dynamic>('/companion/date-reaction', queryParameters: {'date': ymd});
    return DateReaction.fromJson((res.data as Map).cast<String, dynamic>());
  } on DioException catch (e) {
    throw mapDioError(e);
  }
});
