import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/companion/widgets/glow_rail.dart';
import '../../core/relationships/relationship_models.dart';
import '../../core/relationships/relationship_repository.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/glass.dart';
import '../../core/timeline/timeline_models.dart';

/// One person's story (Sprint 7 + UI-X) — people first, money last. A glowing hero,
/// then Memories → Timeline → Coming up → and only then any financial history.
class RelationshipDetailScreen extends ConsumerWidget {
  const RelationshipDetailScreen({super.key, required this.name});
  final String name;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(relationshipDetailProvider(name));
    return CompanionScaffold(
      title: name,
      commentary: async.valueOrNull?.companionNote ?? 'Let me gather your history with $name…',
      mood: CompanionMood.happy,
      child: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => Center(
          child: FilledButton.tonal(
              onPressed: () => ref.invalidate(relationshipDetailProvider(name)), child: const Text('Retry'))),
        data: (r) => ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 36),
          children: [
            _Hero(r: r).animate().fadeIn(duration: 350.ms).slideY(begin: .1, end: 0),
            if (r.memories.isNotEmpty) ...[
              const _Title('Memories'),
              GlassCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                for (final m in r.memories)
                  Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Text('💭  $m')),
              ])).animate(delay: 120.ms).fadeIn(duration: 350.ms),
            ],
            if (r.timeline.isNotEmpty) ...[
              const _Title('Timeline'),
              for (var i = 0; i < r.timeline.length; i++)
                _RailLine(e: r.timeline[i], index: i, last: i == r.timeline.length - 1),
            ],
            if (r.future.isNotEmpty) ...[
              const _Title('Coming up'),
              for (var i = 0; i < r.future.length; i++)
                _RailLine(e: r.future[i], index: i, last: i == r.future.length - 1),
            ],
            // Money — only if there's any, and never in the hero.
            if (r.trust != null) ...[
              const _Title('Money between you'),
              _TrustCard(trust: r.trust!, note: r.trustNote).animate(delay: 120.ms).fadeIn(duration: 350.ms),
            ],
          ],
        ),
      ),
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero({required this.r});
  final RelationshipDetail r;
  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    return GlassCard(
      radius: 26,
      padding: const EdgeInsets.all(18),
      gradient: LinearGradient(
        colors: [AppColors.accent.withValues(alpha: 0.38), AppColors.primary.withValues(alpha: 0.16)],
        begin: Alignment.topLeft, end: Alignment.bottomRight,
      ),
      borderColor: AppColors.accent.withValues(alpha: 0.4),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            width: 64, height: 64,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(colors: [AppColors.accent, AppColors.accent.withValues(alpha: 0.45)]),
              boxShadow: [BoxShadow(color: AppColors.accent.withValues(alpha: 0.6), blurRadius: 26, spreadRadius: 2)],
            ),
            alignment: Alignment.center,
            child: Text(r.name.isNotEmpty ? r.name[0].toUpperCase() : '❤️',
                style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: Colors.white)),
          ),
          const SizedBox(width: 16),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(r.name, style: tt.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
            Text([if (r.relationshipType != null) r.relationshipType!, r.companionNote.replaceAll('.', '')]
                .where((s) => s.isNotEmpty).join(' · '), style: tt.bodySmall),
          ])),
        ]),
      ]),
    );
  }
}

class _TrustCard extends StatelessWidget {
  const _TrustCard({required this.trust, required this.note});
  final TrustProfile trust;
  final String note;
  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final pct = trust.total == 0 ? 0.0 : trust.repaid / trust.total;
    return GlassCard(
      child: Row(children: [
        SizedBox(
          width: 52, height: 52,
          child: Stack(alignment: Alignment.center, children: [
            CircularProgressIndicator(value: pct, strokeWidth: 5,
                backgroundColor: Colors.white.withValues(alpha: 0.1), color: AppColors.secondary),
            const Text('🤝', style: TextStyle(fontSize: 18)),
          ]),
        ),
        const SizedBox(width: 14),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(trust.label, style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
          Text('${trust.repaid}/${trust.total} repayments'
              '${trust.outstanding != null ? ' · ${trust.outstanding} outstanding' : ''}', style: tt.bodySmall),
          if (note.isNotEmpty) Text(note, style: tt.bodySmall),
        ])),
      ]),
    );
  }
}

class _Title extends StatelessWidget {
  const _Title(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 18, bottom: 8, left: 2),
        child: Text(text, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
      );
}

/// One shared moment on the person's glowing rail.
class _RailLine extends StatelessWidget {
  const _RailLine({required this.e, required this.index, required this.last});
  final TimelineEntry e;
  final int index;
  final bool last;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    final color = colorForKind(e.kind);

    final card = Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        color: Colors.white.withValues(alpha: e.isFuture ? 0.03 : 0.05),
        border: Border.all(color: Colors.white.withValues(alpha: e.isFuture ? 0.12 : 0.08)),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(e.title, style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
          if (e.date != null)
            Padding(padding: const EdgeInsets.only(top: 3),
                child: Text(e.date!, style: tt.labelSmall?.copyWith(color: cs.onSurfaceVariant))),
        ])),
        if (e.isFuture)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.22), borderRadius: BorderRadius.circular(10)),
            child: Text('Ahead', style: tt.labelSmall),
          ),
      ]),
    );

    return JourneyRow(
      emoji: e.icon,
      color: color,
      dim: e.isFuture,
      last: last,
      nodeSize: 34,
      child: card,
    ).animate(delay: (index.clamp(0, 10) * 50).ms).fadeIn(duration: 320.ms).slideX(begin: 0.05, end: 0);
  }
}
