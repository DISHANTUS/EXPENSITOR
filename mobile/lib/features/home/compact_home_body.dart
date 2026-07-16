import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/format/money.dart';
import '../../core/home/dismissed_predictions.dart';
import '../../core/notifications/local_notification_service.dart';
import '../../core/settings/settings_repository.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/glass.dart';
import '../advisor/advisor_chat_repository.dart';
import '../advisor/widgets/follow_up_card.dart';
import '../calendar/calendar_models.dart';
import '../calendar/calendar_repository.dart';
import 'add_event_sheet.dart';
import 'dashboard_models.dart';
import 'dashboard_repository.dart';
import 'home_screen.dart';
import 'predicted_expense_repository.dart';
import 'widgets/spend_confirm_card.dart';

/// Every Home open after the first one today: a quick "where do I stand"
/// check instead of the full planning calendar — the safe-to-spend hero,
/// what's already gone out today, this week at a glance, and (once the
/// companion has anything to ask) a one-tap check-in. The full calendar is
/// always one drawer tap away (see AppDrawer's Home item).
class CompactHomeBody extends ConsumerWidget {
  const CompactHomeBody({super.key, required this.brief});
  final DailyBrief? brief;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = AppColors.active;
    final today = brief?.today;
    final dueFollowUps = ref.watch(dueFollowUpsProvider);

    // A spending_shift item needs a reason but shouldn't interrupt right now
    // — schedule (once per advice id) a local nudge for the user's next
    // stated free-time slot instead. Fires only when the list actually
    // changes, not on every rebuild.
    ref.listen(dueFollowUpsProvider, (_, next) {
      final list = next.valueOrNull ?? const [];
      if (list.isEmpty) return;
      final prefs = ref.read(userSettingsProvider).valueOrNull?.notificationPreferences ?? const {};
      final weekday = (prefs['free_time_weekday'] as String?) ?? 'evening';
      final weekend = (prefs['free_time_weekend'] as String?) ?? 'afternoon';
      for (final q in list) {
        if (q.kind != 'spending_shift') continue;
        ref.read(localNotificationServiceProvider).scheduleExplainReminder(
              adviceId: q.id,
              title: 'Advary noticed something',
              body: q.question,
              weekdaySlot: weekday,
              weekendSlot: weekend,
            );
      }
    });

    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
      children: [
        SafeToSpendHero(brief: brief),
        const _WeekStrip(),
        const SizedBox(height: 10),
        if (today != null && today.spentToday > 0)
          GlassCard(
            margin: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('SPENT TODAY',
                    style: TextStyle(color: p.muted, fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1.0)),
                const SizedBox(height: 8),
                for (final c in today.byCategory)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(c.label, style: TextStyle(color: p.on)),
                        Text(formatMoneyValue(c.amount, today.currency),
                            style: TextStyle(color: p.on, fontWeight: FontWeight.w700)),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        _PredictedHabits(currency: brief?.currency ?? today?.currency ?? 'INR'),
        dueFollowUps.when(
          data: (list) => Column(children: [
            for (final q in list.take(2))
              FollowUpCard(
                q,
                onAnswer: (v, {detail}) async {
                  try {
                    final ack =
                        await ref.read(advisorChatRepositoryProvider).answerFollowUp(q.id, v, detail: detail);
                    // Too thin a reason: keep the card open and say so, rather
                    // than silently dropping what they typed.
                    if (ack.needsMoreDetail) return ack.acknowledged;
                    await ref.read(localNotificationServiceProvider).cancelForAdvice(q.id);
                    ref.invalidate(dueFollowUpsProvider);
                    return null;
                  } on AppError catch (e) {
                    return e.message;   // the typed reason stays put, ready to retry
                  }
                },
              ),
          ]),
          loading: () => const SizedBox.shrink(),
          error: (_, __) => const SizedBox.shrink(),
        ),
        const SizedBox(height: 16),
        Center(
          child: FilledButton.icon(
            onPressed: () => showAddEventSheet(context),
            icon: const Icon(Icons.add),
            label: const Text('Add today\'s spending'),
          ),
        ),
      ],
    );
  }
}

/// Learned daily habits offered for one-tap confirmation ("Is the ₹200 for
/// travel over?"). Only appears once there's ~2 weeks of history to learn
/// from, and quietly shows nothing at all when there's no habit for today.
class _PredictedHabits extends ConsumerWidget {
  const _PredictedHabits({required this.currency});
  final String currency;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final predicted = ref.watch(predictedTodayProvider).valueOrNull ?? const [];
    final dismissed = ref.watch(dismissedPredictionsProvider);
    final live = predicted.where((p) => !dismissed.contains(p.categoryId)).toList();
    if (live.isEmpty) return const SizedBox.shrink();

    return Column(children: [
      for (final p in live.take(2))
        SpendConfirmCard(
          key: ValueKey(p.categoryId),
          prediction: p,
          currency: currency,
          onDismiss: () => ref.read(dismissedPredictionsProvider.notifier).dismiss(p.categoryId),
          onConfirm: (amount) async {
            try {
              await ref.read(predictedExpenseRepositoryProvider)
                  .confirm(categoryId: p.categoryId, amount: amount, currency: currency);
              // Refresh what the rest of the screen shows about today.
              ref.invalidate(predictedTodayProvider);
              ref.invalidate(dailyBriefProvider);
              return null;
            } on AppError catch (e) {
              return e.message;
            }
          },
        ),
    ]);
  }
}

/// This week (Mon–Sun) at a glance, reusing the same monthViewProvider data
/// the full calendar already fetches — no separate endpoint needed.
class _WeekStrip extends ConsumerWidget {
  const _WeekStrip();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = DateTime.now();
    final monday = DateTime(now.year, now.month, now.day).subtract(Duration(days: now.weekday - 1));
    final days = List.generate(7, (i) => monday.add(Duration(days: i)));
    // A week can straddle two calendar months — fetch both, cheaply cached.
    final months = {for (final d in days) (year: d.year, month: d.month)};
    final views = {for (final ym in months) ym: ref.watch(monthViewProvider(ym)).valueOrNull};
    final p = AppColors.active;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          for (final d in days)
            _DayDot(
              day: d,
              isToday: _isSameDay(d, now),
              cell: views[(year: d.year, month: d.month)]?.cell(d),
              accent: p.primary,
              muted: p.muted,
              on: p.on,
            ),
        ],
      ),
    );
  }

  static bool _isSameDay(DateTime a, DateTime b) => a.year == b.year && a.month == b.month && a.day == b.day;
}

class _DayDot extends StatelessWidget {
  const _DayDot({
    required this.day, required this.isToday, required this.cell,
    required this.accent, required this.muted, required this.on,
  });
  final DateTime day;
  final bool isToday;
  final DayCell? cell;
  final Color accent;
  final Color muted;
  final Color on;

  static const _labels = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

  @override
  Widget build(BuildContext context) {
    final dotColor = switch (cell?.classification) {
      'over' => Colors.redAccent,
      'saved' => Colors.amber,
      _ => muted.withValues(alpha: 0.5),
    };
    return GestureDetector(
      onTap: () => context.go('/date/${day.toIso8601String().split('T').first}'),
      child: Column(
        children: [
          Text(_labels[day.weekday - 1], style: TextStyle(color: muted, fontSize: 11)),
          const SizedBox(height: 4),
          Container(
            width: 30, height: 30,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: isToday ? accent.withValues(alpha: 0.22) : null,
              border: isToday ? Border.all(color: accent, width: 1.4) : null,
            ),
            child: Text('${day.day}', style: TextStyle(color: on, fontWeight: isToday ? FontWeight.w800 : FontWeight.w500)),
          ),
          const SizedBox(height: 3),
          Container(width: 5, height: 5, decoration: BoxDecoration(shape: BoxShape.circle, color: dotColor)),
        ],
      ),
    );
  }
}
