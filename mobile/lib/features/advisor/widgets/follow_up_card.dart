import 'package:flutter/material.dart';

import '../chat_models.dart';

/// Learning-loop check-in (4b-5a): the companion asks "what happened?" about a
/// past piece of advice. Tapping Yes/Partially/No records a Phase-E Outcome.
class FollowUpCard extends StatelessWidget {
  const FollowUpCard(this.q, {super.key, required this.onAnswer, this.answered});
  final FollowUpQuestion q;
  final void Function(String value) onAnswer;   // yes | partial | no
  final String? answered;                        // ack text once answered (disables chips)

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      color: cs.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.history_outlined, size: 18, color: cs.primary),
              const SizedBox(width: 6),
              const Text('Quick check-in', style: TextStyle(fontWeight: FontWeight.w600)),
            ]),
            const SizedBox(height: 8),
            Text(q.question),
            const SizedBox(height: 10),
            if (answered == null)
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final o in q.options)
                  ActionChip(label: Text(o.label), onPressed: () => onAnswer(o.value)),
              ])
            else
              Row(children: [
                Icon(Icons.check_circle_outline, size: 16, color: cs.primary),
                const SizedBox(width: 6),
                Expanded(child: Text(answered!, style: tt.bodyMedium)),
              ]),
          ],
        ),
      ),
    );
  }
}
