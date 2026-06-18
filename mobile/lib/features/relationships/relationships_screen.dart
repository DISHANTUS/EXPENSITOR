import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/relationships/relationship_models.dart';
import '../../core/relationships/relationship_repository.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/glass.dart';

/// The people in the user's story (Sprint 7 + UI-X-2) — glowing avatars, people
/// first. Tap anyone for their page.
class RelationshipsScreen extends ConsumerWidget {
  const RelationshipsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(relationshipsProvider);
    return CompanionScaffold(
      title: 'People',
      commentary: 'The people in your story — tap anyone to see your history together.',
      mood: CompanionMood.happy,
      child: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => Center(
          child: FilledButton.tonal(
              onPressed: () => ref.invalidate(relationshipsProvider), child: const Text('Retry'))),
        data: (people) => people.isEmpty
            ? const Center(child: Padding(padding: EdgeInsets.all(32),
                child: Text('No people yet — lend, plan an outing, or add someone and I’ll track them here.',
                    textAlign: TextAlign.center)))
            : RefreshIndicator(
                onRefresh: () async => ref.invalidate(relationshipsProvider),
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(14, 10, 14, 32),
                  children: [
                    for (var i = 0; i < people.length; i++)
                      _PersonCard(person: people[i])
                          .animate(delay: (i.clamp(0, 12) * 50).ms)
                          .fadeIn(duration: 320.ms)
                          .slideY(begin: 0.08, end: 0, curve: Curves.easeOut),
                  ],
                ),
              ),
      ),
    );
  }
}

class _PersonCard extends StatelessWidget {
  const _PersonCard({required this.person});
  final RelationshipSummary person;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    final subtitle = [
      if (person.relationshipType != null) person.relationshipType!,
      '${person.memoryCount} ${person.memoryCount == 1 ? 'memory' : 'memories'}',
      if (person.futureCount > 0) '${person.futureCount} upcoming',
    ].join(' · ');

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassCard(
        padding: const EdgeInsets.all(14),
        onTap: () => context.go('/relationship/${Uri.encodeComponent(person.name)}'),
        child: Row(
          children: [
            Container(
              width: 48, height: 48, alignment: Alignment.center,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(colors: [AppColors.accent, AppColors.accent.withValues(alpha: 0.45)]),
                boxShadow: [BoxShadow(color: AppColors.accent.withValues(alpha: 0.5), blurRadius: 18, spreadRadius: 1)],
              ),
              child: Text(person.name.isNotEmpty ? person.name[0].toUpperCase() : '?',
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: Colors.white)),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(person.name, style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 2),
                  Text(subtitle, style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant)),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: cs.onSurfaceVariant),
          ],
        ),
      ),
    );
  }
}
