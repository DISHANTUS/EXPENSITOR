import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/companion/widgets/glow_rail.dart';
import '../../core/future_me/future_me_models.dart';
import '../../core/future_me/future_me_repository.dart';
import '../../core/theme/app_theme.dart';

/// Future Me (Sprint 6b): the forward half of the life story — three paths
/// (current / optimistic / conservative), the levers that change them, and the
/// milestones ahead (goal ETAs, upcoming events, user life events, forecasts).
class FutureMeScreen extends ConsumerWidget {
  const FutureMeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(futureMeProvider);
    return CompanionScaffold(
      title: 'Future Me',
      commentary: async.valueOrNull?.headline ?? 'Let me look ahead for you…',
      mood: CompanionMood.excited,
      child: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('I couldn’t look ahead just now.'),
            const SizedBox(height: 8),
            FilledButton.tonal(onPressed: () => ref.invalidate(futureMeProvider), child: const Text('Retry')),
          ]),
        ),
        data: (fm) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(futureMeProvider),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
            children: [
              if (fm.paths.isNotEmpty) ...[
                const _SectionTitle('Where you’re headed'),
                for (var i = 0; i < fm.paths.length; i++)
                  _PathCard(path: fm.paths[i], currency: fm.currency)
                      .animate(delay: (i * 90).ms)
                      .fadeIn(duration: 380.ms)
                      .slideY(begin: 0.1, end: 0, curve: Curves.easeOut),
              ] else
                const _Note('I need a bit more history (and some positive savings) before I can project your paths.'),
              if (fm.levers.isNotEmpty) ...[
                const SizedBox(height: 16),
                const _SectionTitle('What changes this future?'),
                Wrap(spacing: 8, runSpacing: 8, children: [for (final l in fm.levers) Chip(label: Text(l.label))]),
              ],
              if (fm.milestones.isNotEmpty) ...[
                const SizedBox(height: 18),
                const _SectionTitle('The journey ahead'),
                for (var i = 0; i < fm.milestones.length; i++)
                  _MilestoneRail(m: fm.milestones[i], last: i == fm.milestones.length - 1)
                      .animate(delay: (i.clamp(0, 10) * 70).ms)
                      .fadeIn(duration: 360.ms)
                      .slideX(begin: 0.06, end: 0, curve: Curves.easeOut),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 4, bottom: 8),
        child: Text(text, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
      );
}

class _PathCard extends StatelessWidget {
  const _PathCard({required this.path, required this.currency});
  final FutureMePath path;
  final String currency;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    final isCurrent = path.mode == 'current';
    final (gradient, glow, border) = switch (path.mode) {
      'optimistic' => (
          LinearGradient(colors: [AppColors.secondary.withValues(alpha: 0.30), AppColors.primary.withValues(alpha: 0.12)],
              begin: Alignment.topLeft, end: Alignment.bottomRight),
          AppColors.secondary, AppColors.secondary.withValues(alpha: 0.45)),
      'conservative' => (
          LinearGradient(colors: [Colors.white.withValues(alpha: 0.06), Colors.white.withValues(alpha: 0.03)]),
          Colors.transparent, Colors.white.withValues(alpha: 0.12)),
      _ => (
          LinearGradient(colors: [AppColors.primary.withValues(alpha: 0.38), AppColors.secondary.withValues(alpha: 0.18)],
              begin: Alignment.topLeft, end: Alignment.bottomRight),
          AppColors.primary, AppColors.primary),
    };
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 11),
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: border, width: isCurrent ? 1.5 : 1),
        boxShadow: glow == Colors.transparent ? null
            : [BoxShadow(color: glow.withValues(alpha: 0.28), blurRadius: 22, offset: const Offset(0, 8))],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(path.label, style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w700))),
              Text(path.eta ?? 'No date at this rate',
                  style: tt.labelLarge?.copyWith(color: path.eta == null ? cs.error : cs.onSurface)),
            ],
          ),
          if (path.monthlyRate.isNotEmpty)
            Padding(padding: const EdgeInsets.only(top: 2),
                child: Text('$currency ${path.monthlyRate}/month', style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant))),
          if (path.narrative.isNotEmpty)
            Padding(padding: const EdgeInsets.only(top: 6), child: Text(path.narrative, style: tt.bodyMedium)),
        ],
      ),
    );
  }
}

/// A milestone on the glowing journey path: `2028 ──🎯 Japan Fund`. Goal/forecast
/// milestones glow as highlights; everything ahead reads as luminous and hopeful.
class _MilestoneRail extends StatelessWidget {
  const _MilestoneRail({required this.m, required this.last});
  final FutureMeMilestone m;
  final bool last;
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    final color = colorForKind(m.kind);
    final highlight = m.kind == 'goal' || m.kind == 'forecast' || m.kind == 'life_event';
    final year = (m.date != null && m.date!.length >= 4) ? m.date!.substring(0, 4) : '';

    return JourneyRow(
      emoji: m.icon,
      color: color,
      highlight: highlight,
      last: last,
      leading: Text(year, style: tt.labelLarge?.copyWith(fontWeight: FontWeight.w800, color: color)),
      child: Container(
        padding: const EdgeInsets.all(13),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          gradient: highlight
              ? LinearGradient(
                  colors: [color.withValues(alpha: 0.26), AppColors.primary.withValues(alpha: 0.10)],
                  begin: Alignment.topLeft, end: Alignment.bottomRight)
              : null,
          color: highlight ? null : Colors.white.withValues(alpha: 0.05),
          border: Border.all(color: color.withValues(alpha: highlight ? 0.45 : 0.14)),
          boxShadow: highlight
              ? [BoxShadow(color: color.withValues(alpha: 0.22), blurRadius: 18, offset: const Offset(0, 6))]
              : null,
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(m.title, style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w700)),
          if (m.detail.isNotEmpty)
            Padding(padding: const EdgeInsets.only(top: 2),
                child: Text(m.detail, style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant))),
          if (m.date != null)
            Padding(padding: const EdgeInsets.only(top: 4),
                child: Text(m.date!, style: tt.labelSmall?.copyWith(color: cs.onSurfaceVariant))),
        ]),
      ),
    );
  }
}

class _Note extends StatelessWidget {
  const _Note(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Text(text, style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant)),
      );
}
