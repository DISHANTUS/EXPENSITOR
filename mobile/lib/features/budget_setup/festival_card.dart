import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../core/theme/glass.dart';
import 'festival_repository.dart';

/// Festivals coming up, on the Planning page — because knowing Diwali is in 12
/// weeks is only useful where you can actually do something about it.
///
/// Renders nothing at all when there's nothing near enough to matter, or when
/// the festival calendar has run out of years. Silence beats a guessed date.
class FestivalCard extends ConsumerWidget {
  const FestivalCard({super.key, this.onPlan});

  /// Tapping "Plan for it" hands the festival's name up to the Planning flow so
  /// the user doesn't retype what Advary just told them.
  final void Function(String festivalName)? onPlan;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = AppColors.active;
    final festivals = ref.watch(festivalsProvider).valueOrNull;
    if (festivals == null || !festivals.ready || festivals.upcoming.isEmpty) {
      return const SizedBox.shrink();
    }

    final next = festivals.upcoming.first;
    final rest = festivals.upcoming.skip(1).toList();

    return GlassCard(
      margin: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(Icons.celebration_outlined, size: 18, color: p.primary),
            const SizedBox(width: 8),
            Text('Coming up', style: TextStyle(color: p.on, fontWeight: FontWeight.w700, fontSize: 15)),
          ]),
          const SizedBox(height: 8),
          // The backend's sentence, verbatim. It already knows whether there's
          // history to quote and whether the date can be promised.
          Text(next.line, style: TextStyle(color: p.on, height: 1.4, fontSize: 13.5)),
          if (rest.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Then ${rest.map((f) => '${f.name} (${f.daysAway}d)').join(' · ')}',
              style: TextStyle(color: p.muted, fontSize: 12),
            ),
          ],
          if (onPlan != null) ...[
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerLeft,
              child: OutlinedButton.icon(
                onPressed: () => onPlan!(next.name),
                icon: const Icon(Icons.savings_outlined, size: 16),
                label: Text('Plan for ${next.name}'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
