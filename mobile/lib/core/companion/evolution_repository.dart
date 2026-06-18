import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';

/// A single deterministic observation Advary makes about the user's journey.
class ReflectionLine {
  const ReflectionLine({required this.icon, required this.text});
  factory ReflectionLine.fromJson(Map<String, dynamic> j) =>
      ReflectionLine(icon: (j['icon'] ?? '✨').toString(), text: (j['text'] ?? '').toString());
  final String icon;
  final String text;
}

class ChapterProgress {
  const ChapterProgress({
    required this.label,
    this.subtitle = '',
    this.started,
    this.progress,
    this.moments = 0,
  });
  factory ChapterProgress.fromJson(Map<String, dynamic> j) => ChapterProgress(
        label: (j['label'] ?? '').toString(),
        subtitle: (j['subtitle'] ?? '').toString(),
        started: j['started']?.toString(),
        progress: (j['progress'] as num?)?.toInt(),
        moments: (j['moments'] as num?)?.toInt() ?? 0,
      );
  final String label;
  final String subtitle;
  final String? started;
  final int? progress;     // 0–100
  final int moments;
}

class Milestone {
  const Milestone({required this.icon, required this.label, this.date, this.tense = 'past'});
  factory Milestone.fromJson(Map<String, dynamic> j) => Milestone(
        icon: (j['icon'] ?? '⭐').toString(),
        label: (j['label'] ?? '').toString(),
        date: j['date']?.toString(),
        tense: (j['tense'] ?? 'past').toString(),
      );
  final String icon;
  final String label;
  final String? date;
  final String tense;      // past | future
  bool get isFuture => tense == 'future';
}

class EvolutionView {
  const EvolutionView({
    required this.daysWithAdvary,
    required this.reflections,
    this.currentChapter,
    this.longestChapter,
    this.milestones = const [],
  });
  factory EvolutionView.fromJson(Map<String, dynamic> j) => EvolutionView(
        daysWithAdvary: (j['days_with_advary'] as num?)?.toInt() ?? 1,
        reflections: ((j['reflections'] as List?) ?? const [])
            .map((e) => ReflectionLine.fromJson((e as Map).cast<String, dynamic>()))
            .toList(),
        currentChapter: j['current_chapter'] == null
            ? null
            : ChapterProgress.fromJson((j['current_chapter'] as Map).cast<String, dynamic>()),
        longestChapter: j['longest_chapter']?.toString(),
        milestones: ((j['milestones'] as List?) ?? const [])
            .map((e) => Milestone.fromJson((e as Map).cast<String, dynamic>()))
            .toList(),
      );
  final int daysWithAdvary;
  final List<ReflectionLine> reflections;
  final ChapterProgress? currentChapter;
  final String? longestChapter;
  final List<Milestone> milestones;
}

class MonthlyReflection {
  const MonthlyReflection({
    required this.monthLabel,
    required this.available,
    required this.headline,
    this.withinBudgetDays = 0,
    this.trackedDays = 0,
    this.biggestWin,
    this.mostActiveRelationship,
    this.mostImprovedArea,
  });
  factory MonthlyReflection.fromJson(Map<String, dynamic> j) => MonthlyReflection(
        monthLabel: (j['month_label'] ?? '').toString(),
        available: j['available'] == true,
        headline: (j['headline'] ?? '').toString(),
        withinBudgetDays: (j['within_budget_days'] as num?)?.toInt() ?? 0,
        trackedDays: (j['tracked_days'] as num?)?.toInt() ?? 0,
        biggestWin: j['biggest_win']?.toString(),
        mostActiveRelationship: j['most_active_relationship']?.toString(),
        mostImprovedArea: j['most_improved_area']?.toString(),
      );
  final String monthLabel;
  final bool available;
  final String headline;
  final int withinBudgetDays;
  final int trackedDays;
  final String? biggestWin;
  final String? mostActiveRelationship;
  final String? mostImprovedArea;
}

final evolutionProvider = FutureProvider.autoDispose<EvolutionView>((ref) async {
  try {
    final res = await ref.watch(dioProvider).get<dynamic>('/companion/evolution');
    return EvolutionView.fromJson((res.data as Map).cast<String, dynamic>());
  } on DioException catch (e) {
    throw mapDioError(e);
  }
});

final monthlyReflectionProvider = FutureProvider.autoDispose<MonthlyReflection>((ref) async {
  try {
    final res = await ref.watch(dioProvider).get<dynamic>('/companion/monthly-reflection');
    return MonthlyReflection.fromJson((res.data as Map).cast<String, dynamic>());
  } on DioException catch (e) {
    throw mapDioError(e);
  }
});
