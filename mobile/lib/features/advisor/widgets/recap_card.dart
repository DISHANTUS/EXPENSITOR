import 'package:flutter/material.dart';

import '../chat_models.dart';

/// Companion recap (4b-5b): "what do you know about me?" led by a Financial
/// Identity section, then goals / lessons / achievements / relationships.
class RecapCard extends StatelessWidget {
  const RecapCard(this.recap, {super.key, this.onForgetLesson});
  final CompanionRecap recap;
  final void Function(String lessonId)? onForgetLesson;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    final fi = recap.financialIdentity;
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Financial Identity — the lead.
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: cs.primaryContainer, borderRadius: BorderRadius.circular(12)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Your financial identity', style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  if (fi.focusAreas.isNotEmpty) _line('Focused on', fi.focusAreas.join(', ')),
                  if (fi.strongestHabit != null) _line('Strongest habit', fi.strongestHabit!),
                  if (fi.currentChallenge != null) _line('Current challenge', fi.currentChallenge!),
                  if (fi.focusAreas.isEmpty && fi.strongestHabit == null && fi.currentChallenge == null)
                    Text('Still getting to know you — keep logging.', style: tt.bodySmall),
                ],
              ),
            ),
            if (recap.goals.isNotEmpty) ...[
              const SizedBox(height: 12),
              _section(context, '🎯 Goals', recap.goals),
            ],
            if (recap.achievements.isNotEmpty) ...[
              const SizedBox(height: 10),
              _section(context, '🏆 Achievements', recap.achievements.map((a) => a.label).toList()),
            ],
            if (recap.habits.isNotEmpty) ...[
              const SizedBox(height: 10),
              _section(context, '🔁 Habits', recap.habits),
            ],
            if (recap.lessons.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text('💡 Lessons you’ve taught me', style: tt.labelLarge),
              const SizedBox(height: 4),
              for (final l in recap.lessons)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Expanded(child: Text('• ${l.lesson}  (${l.confidence})', style: tt.bodySmall)),
                    if (onForgetLesson != null)
                      InkWell(
                        onTap: () => onForgetLesson!(l.id),
                        child: Padding(
                          padding: const EdgeInsets.only(left: 6),
                          child: Icon(Icons.close, size: 16, color: cs.outline),
                        ),
                      ),
                  ]),
                ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _line(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 1),
        child: RichText(
          text: TextSpan(style: const TextStyle(color: Colors.black87, fontSize: 13), children: [
            TextSpan(text: '$label: ', style: const TextStyle(fontWeight: FontWeight.w600)),
            TextSpan(text: value),
          ]),
        ),
      );

  Widget _section(BuildContext context, String title, List<String> items) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 4),
          for (final it in items) Text('• $it', style: Theme.of(context).textTheme.bodySmall),
        ],
      );
}
