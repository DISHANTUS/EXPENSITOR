import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/theme/glass.dart';
import '../daily_report_repository.dart';

/// "How today went" — the end-of-day report on the compact view: what you kept
/// against today's allowance, whether that's a run, and what it leaves for the
/// goal you're closest to.
///
/// The wording comes from the backend rather than being assembled here, because
/// the honest version depends on things only the server knows (is the day over,
/// is there an allowance at all, is the goal past its date). Restating those
/// numbers in the UI is how the two drift apart and start contradicting.
class DailyReportCard extends ConsumerWidget {
  const DailyReportCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final report = ref.watch(dailyReportProvider).valueOrNull;
    // No skeleton and no error state: this is a summary of things shown
    // elsewhere on the page, so a spinner or an apology costs more than it's
    // worth. It simply isn't there until it has something true to say.
    if (report == null || report.lines.isEmpty) return const SizedBox.shrink();

    final p = AppColors.active;
    final over = report.status == 'over';
    final accent = over ? const Color(0xFFE57373) : p.primary;

    return GlassCard(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(report.dayDone ? Icons.nightlight_round : Icons.wb_sunny_outlined, size: 18, color: accent),
            const SizedBox(width: 8),
            Text(
              // Never call it a wrap-up while the day can still go wrong.
              report.dayDone ? 'How today went' : 'Today so far',
              style: TextStyle(color: p.on, fontWeight: FontWeight.w700, fontSize: 15),
            ),
            const Spacer(),
            if (report.streakDays >= 2)
              _Pill(text: '${report.streakDays} day run', color: p.primary),
          ]),
          const SizedBox(height: 10),
          for (final line in report.lines)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Container(
                    width: 4,
                    height: 4,
                    decoration: BoxDecoration(color: p.muted, shape: BoxShape.circle),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(child: Text(line, style: TextStyle(color: p.on, height: 1.4, fontSize: 13.5))),
              ]),
            ),
          if (report.goal != null && (double.tryParse(report.goal!.remaining) ?? 0) > 0) ...[
            const SizedBox(height: 6),
            _GoalBar(report: report),
          ],
        ],
      ),
    );
  }
}

/// How far along the nearest goal is. Derived straight from the two numbers the
/// report already states, so the bar can't tell a different story from the text
/// directly above it.
class _GoalBar extends StatelessWidget {
  const _GoalBar({required this.report});
  final DailyReport report;

  @override
  Widget build(BuildContext context) {
    final p = AppColors.active;
    final goal = report.goal!;
    final target = double.tryParse(goal.targetAmount) ?? 0;
    final remaining = double.tryParse(goal.remaining) ?? 0;
    if (target <= 0) return const SizedBox.shrink();
    final progress = ((target - remaining) / target).clamp(0.0, 1.0);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: progress,
            minHeight: 6,
            backgroundColor: AppColors.hairline(0.12),
            valueColor: AlwaysStoppedAnimation(p.primary),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          '${goal.name} · ${(progress * 100).round()}% there',
          style: TextStyle(color: p.muted, fontSize: 12),
        ),
      ],
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({required this.text, required this.color});
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.18),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(text, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w700)),
    );
  }
}
