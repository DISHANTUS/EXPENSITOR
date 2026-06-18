import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_orb.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/companion/evolution_repository.dart';
import '../../core/companion/widgets/glow_rail.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/glass.dart';

/// Your Journey with Advary (Sprint 8 — Companion Evolution). Deterministic
/// reflections, the chapter you're living, the milestones Advary remembers, and
/// a month-in-review. Meaningful observations from real data — never fake feeling.
class JourneyScreen extends ConsumerWidget {
  const JourneyScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(evolutionProvider);
    return CompanionScaffold(
      title: 'Your Journey',
      commentary: 'Here’s what I’ve come to know about your journey so far.',
      mood: CompanionMood.happy,
      child: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => Center(
          child: FilledButton.tonal(
              onPressed: () => ref.invalidate(evolutionProvider), child: const Text('Retry'))),
        data: (e) => RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(evolutionProvider);
            ref.invalidate(monthlyReflectionProvider);
          },
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
            children: [
              _ReflectionHero(e: e).animate().fadeIn(duration: 400.ms).slideY(begin: 0.08, end: 0),
              if (e.currentChapter != null) ...[
                const _Title('The chapter you’re in'),
                _ChapterCard(c: e.currentChapter!).animate(delay: 120.ms).fadeIn(duration: 380.ms),
              ],
              if (e.milestones.isNotEmpty) ...[
                const _Title('Milestones I remember'),
                for (var i = 0; i < e.milestones.length; i++)
                  _MilestoneRow(m: e.milestones[i], last: i == e.milestones.length - 1)
                      .animate(delay: (i.clamp(0, 10) * 60).ms)
                      .fadeIn(duration: 340.ms)
                      .slideX(begin: 0.06, end: 0),
              ],
              const _Title('This month'),
              const _MonthlyCard(),
            ],
          ),
        ),
      ),
    );
  }
}

class _ReflectionHero extends StatelessWidget {
  const _ReflectionHero({required this.e});
  final EvolutionView e;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    return GlassCard(
      radius: 24,
      gradient: LinearGradient(
        colors: [AppColors.primary.withValues(alpha: 0.30), AppColors.secondary.withValues(alpha: 0.12)],
        begin: Alignment.topLeft, end: Alignment.bottomRight,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const CompanionOrb(state: OrbState.celebrating, size: 60),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${e.daysWithAdvary}',
                        style: tt.headlineMedium?.copyWith(fontWeight: FontWeight.w900, height: 1)),
                    Text('${e.daysWithAdvary == 1 ? 'day' : 'days'} together',
                        style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          for (final r in e.reflections)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(r.icon, style: const TextStyle(fontSize: 16)),
                  const SizedBox(width: 8),
                  Expanded(child: Text(r.text, style: tt.bodyMedium?.copyWith(height: 1.3))),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _ChapterCard extends StatelessWidget {
  const _ChapterCard({required this.c});
  final ChapterProgress c;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    final started = c.started != null && c.started!.length >= 7 ? _prettyMonth(c.started!) : null;
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(c.label, style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w800, color: AppColors.primary)),
          if (c.subtitle.isNotEmpty)
            Padding(padding: const EdgeInsets.only(top: 2),
                child: Text(c.subtitle, style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant))),
          const SizedBox(height: 10),
          Row(
            children: [
              if (started != null)
                Text('Started $started', style: tt.labelMedium?.copyWith(color: cs.onSurfaceVariant)),
              const Spacer(),
              Text('${c.moments} ${c.moments == 1 ? 'moment' : 'moments'}',
                  style: tt.labelMedium?.copyWith(color: cs.onSurfaceVariant)),
            ],
          ),
          if (c.progress != null) ...[
            const SizedBox(height: 10),
            _ProgressBar(value: c.progress! / 100),
            const SizedBox(height: 4),
            Text('${c.progress}% through this chapter',
                style: tt.labelSmall?.copyWith(color: cs.onSurfaceVariant)),
          ],
        ],
      ),
    );
  }

  static String _prettyMonth(String iso) {
    const months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    final parts = iso.split('-');
    final m = int.tryParse(parts[1]) ?? 0;
    return '${m >= 1 && m <= 12 ? months[m] : ''} ${parts[0]}'.trim();
  }
}

class _ProgressBar extends StatelessWidget {
  const _ProgressBar({required this.value});
  final double value;
  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(8),
      child: Stack(
        children: [
          Container(height: 10, color: Colors.white.withValues(alpha: 0.08)),
          FractionallySizedBox(
            widthFactor: value.clamp(0.02, 1.0),
            child: Container(
              height: 10,
              decoration: const BoxDecoration(gradient: AppColors.gradient),
            ),
          ),
        ],
      ),
    );
  }
}

class _MilestoneRow extends StatelessWidget {
  const _MilestoneRow({required this.m, required this.last});
  final Milestone m;
  final bool last;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    final color = m.isFuture ? AppColors.secondary : AppColors.primary;
    return JourneyRow(
      emoji: m.icon,
      color: color,
      highlight: m.isFuture,
      last: last,
      nodeSize: 34,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          color: Colors.white.withValues(alpha: 0.05),
          border: Border.all(color: color.withValues(alpha: 0.18)),
        ),
        child: Row(
          children: [
            Expanded(child: Text(m.label, style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600))),
            if (m.isFuture)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                    color: AppColors.secondary.withValues(alpha: 0.22), borderRadius: BorderRadius.circular(10)),
                child: Text('Ahead', style: tt.labelSmall),
              )
            else if (m.date != null)
              Text(m.date!.split('-').first, style: tt.labelSmall?.copyWith(color: cs.onSurfaceVariant)),
          ],
        ),
      ),
    );
  }
}

class _MonthlyCard extends ConsumerWidget {
  const _MonthlyCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(monthlyReflectionProvider);
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    final r = async.valueOrNull;
    if (r == null) {
      return GlassCard(child: Text('Gathering this month…', style: tt.bodyMedium?.copyWith(color: cs.onSurfaceVariant)));
    }

    if (!r.available) {
      return GlassCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(r.monthLabel, style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(r.headline, style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant)),
        ]),
      );
    }

    final rows = <(String, String)>[
      ('🟢', 'Within budget ${r.withinBudgetDays} ${r.withinBudgetDays == 1 ? 'day' : 'days'}'),
      if (r.biggestWin != null) ('🏆', 'Biggest win: ${r.biggestWin}'),
      if (r.mostActiveRelationship != null) ('❤️', 'Most time with ${r.mostActiveRelationship}'),
      if (r.mostImprovedArea != null) ('📈', 'Most improved: ${r.mostImprovedArea}'),
    ];

    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${r.monthLabel} reflection',
              style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w800, color: AppColors.secondary)),
          const SizedBox(height: 8),
          for (final (icon, text) in rows)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(icon, style: const TextStyle(fontSize: 15)),
                const SizedBox(width: 8),
                Expanded(child: Text(text, style: tt.bodyMedium?.copyWith(height: 1.3))),
              ]),
            ),
        ],
      ),
    ).animate().fadeIn(duration: 380.ms);
  }
}

class _Title extends StatelessWidget {
  const _Title(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 20, bottom: 8, left: 2),
        child: Text(text, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
      );
}
