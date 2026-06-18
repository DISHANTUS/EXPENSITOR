import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/relationships/relationship_repository.dart';

/// The people in the user's story (Sprint 7) — tap one for their page.
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
                  padding: const EdgeInsets.all(12),
                  children: [
                    for (final p in people)
                      Card(
                        child: ListTile(
                          leading: CircleAvatar(child: Text(p.name.isNotEmpty ? p.name[0].toUpperCase() : '?')),
                          title: Text(p.name),
                          subtitle: Text([
                            if (p.relationshipType != null) p.relationshipType!,
                            '${p.memoryCount} ${p.memoryCount == 1 ? 'memory' : 'memories'}',
                            if (p.futureCount > 0) '${p.futureCount} upcoming',
                          ].join(' · ')),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => context.go('/relationship/${Uri.encodeComponent(p.name)}'),
                        ),
                      ),
                  ],
                ),
              ),
      ),
    );
  }
}
