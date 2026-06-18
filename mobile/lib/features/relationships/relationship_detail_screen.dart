import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_scaffold.dart';
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
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          children: [
            _Hero(r: r).animate().fadeIn(duration: 350.ms).slideY(begin: .1, end: 0),
            if (r.memories.isNotEmpty) ...[
              const _Title('Memories'),
              GlassCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                for (final m in r.memories)
                  Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Text('💭  $m')),
              ])),
            ],
            if (r.timeline.isNotEmpty) ...[
              const _Title('Timeline'),
              for (final e in r.timeline) _Line(e: e),
            ],
            if (r.future.isNotEmpty) ...[
              const _Title('Coming up'),
              for (final e in r.future) _Line(e: e),
            ],
            // Money — only if there's any, and never in the hero.
            if (r.trust != null) ...[
              const _Title('Money between you'),
              _TrustCard(trust: r.trust!, note: r.trustNote),
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
              gradient: const RadialGradient(colors: [AppColors.accent, Color(0xFF7A2A59)]),
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

class _Line extends StatelessWidget {
  const _Line({required this.e});
  final TimelineEntry e;
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Container(
          width: 34, height: 34, alignment: Alignment.center,
          decoration: BoxDecoration(shape: BoxShape.circle, color: Colors.white.withValues(alpha: 0.06),
              boxShadow: [BoxShadow(color: AppColors.accent.withValues(alpha: 0.4), blurRadius: 12)]),
          child: Text(e.icon, style: const TextStyle(fontSize: 17)),
        ),
        const SizedBox(width: 12),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(e.title, style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
          if (e.date != null) Text(e.date!, style: tt.labelSmall?.copyWith(color: cs.onSurfaceVariant)),
        ])),
        if (e.isFuture)
          Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(color: cs.primaryContainer, borderRadius: BorderRadius.circular(10)),
              child: Text('Ahead', style: tt.labelSmall)),
      ]),
    );
  }
}
