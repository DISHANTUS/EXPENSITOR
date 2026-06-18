import 'package:flutter/material.dart';

import '../reaction.dart';

/// The temporary reaction bubble shown over the greeting/commentary on any page.
class ReactionCard extends StatelessWidget {
  const ReactionCard(this.r, {super.key, required this.onDismiss, this.onTap});
  final CompanionReaction r;
  final VoidCallback onDismiss;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    final bg = switch (r.importance) {
      ReactionImportance.achievement => cs.tertiaryContainer,
      ReactionImportance.milestone => cs.primaryContainer,
      ReactionImportance.normal => cs.surface,
    };
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 10, 6, 10),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: cs.primary.withValues(alpha: 0.4)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(r.emoji, style: const TextStyle(fontSize: 20)),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(r.headline, style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
                  if (r.detail.isNotEmpty)
                    Padding(padding: const EdgeInsets.only(top: 2), child: Text(r.detail, style: tt.bodyMedium)),
                ],
              ),
            ),
            IconButton(
              tooltip: 'Dismiss',
              visualDensity: VisualDensity.compact,
              icon: const Icon(Icons.close, size: 18),
              onPressed: onDismiss,
            ),
          ],
        ),
      ),
    );
  }
}
