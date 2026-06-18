import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/facts/fact_sheet.dart';
import '../../core/facts/facts_models.dart';
import '../../core/facts/facts_prefs.dart';
import '../../core/facts/facts_repository.dart';
import '../../core/theme/glass.dart';

/// Today's deterministic fact — stable through the day, rotates tomorrow. Passive
/// discovery under the companion thought; tap for a fresh one.
final _dailyFactProvider = FutureProvider.autoDispose<FactItem?>((ref) async {
  final disabled = await ref.watch(disabledFactCategoriesProvider.future);
  final now = DateTime.now();
  return ref.watch(factsRepositoryProvider).dailyFact(DateTime(now.year, now.month, now.day), disabled: disabled);
});

/// A small "🧠 Did You Know?" card. Hidden until a fact is available, so it never
/// shows an empty box. Tapping opens the fact sheet ("Tell me another").
class DidYouKnowCard extends ConsumerWidget {
  const DidYouKnowCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fact = ref.watch(_dailyFactProvider).valueOrNull;
    if (fact == null) return const SizedBox.shrink();
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 4),
      child: GlassCard(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        onTap: () => showFactSheet(context, initial: fact),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('🧠  Did You Know?',
                    style: tt.labelMedium?.copyWith(
                        color: cs.primary, letterSpacing: 0.4, fontWeight: FontWeight.w700)),
                const Spacer(),
                Text(fact.emoji, style: const TextStyle(fontSize: 14)),
              ],
            ),
            const SizedBox(height: 6),
            Text(fact.text, style: tt.bodyMedium?.copyWith(height: 1.3)),
            const SizedBox(height: 6),
            Align(
              alignment: Alignment.centerRight,
              child: Text('Tap for more →', style: tt.labelSmall?.copyWith(color: cs.onSurfaceVariant)),
            ),
          ],
        ),
      ),
    );
  }
}
