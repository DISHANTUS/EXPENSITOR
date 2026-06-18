import 'package:flutter/material.dart';

import '../../../core/format/money.dart';
import '../chat_models.dart';

/// Forecast turn (4b-4): layered explanation (headline → reasoning → evidence),
/// three Future-Me paths, opportunity cost, and tappable what-if levers.
class ForecastCard extends StatelessWidget {
  const ForecastCard(this.f, {super.key, required this.onLever, required this.onTap, required this.onExplain});
  final Forecast f;
  final void Function(String ref) onLever;       // tapped a lever chip → recalc
  final void Function(String message) onTap;      // tapped a follow-up
  final void Function(String ref) onExplain;

  static const _months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  static String _date(String? iso) {
    if (iso == null || iso.length < 7) return '—';
    final y = iso.substring(0, 4);
    final m = int.tryParse(iso.substring(5, 7)) ?? 0;
    return '${m >= 1 && m <= 12 ? _months[m] : ''} $y'.trim();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    final negative = f.kind == 'negative';
    final headlineColor = negative ? cs.error : cs.primary;

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Level 1 — the headline.
            Row(children: [
              Icon(negative ? Icons.trending_down : Icons.insights_outlined, size: 18, color: headlineColor),
              const SizedBox(width: 6),
              Expanded(child: Text(f.headline, style: tt.titleMedium?.copyWith(color: headlineColor, fontWeight: FontWeight.w700))),
            ]),
            if (f.confidenceNote != null && f.confidenceNote!.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(f.confidenceNote!, style: TextStyle(fontStyle: FontStyle.italic, color: cs.outline, fontSize: 12)),
            ],
            // Level 2 — reasoning (no magic numbers).
            const SizedBox(height: 8),
            Text(f.reasoning),
            if (f.accuracyNote != null && f.accuracyNote!.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(f.accuracyNote!, style: TextStyle(fontStyle: FontStyle.italic, color: cs.outline, fontSize: 12)),
            ],
            // A lesson the user taught, relevant right here (4b-5b).
            if (f.surfacedLesson != null && f.surfacedLesson!.isNotEmpty) ...[
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(color: cs.tertiaryContainer, borderRadius: BorderRadius.circular(10)),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('💡 '),
                  Expanded(child: Text(f.surfacedLesson!, style: tt.bodySmall)),
                ]),
              ),
            ],

            // Three Future-Me paths.
            if (f.scenarios.isNotEmpty) ...[
              const SizedBox(height: 12),
              for (final p in f.scenarios) _PathTile(p, currency: f.currency, dateOf: _date),
            ],

            // Opportunity cost (works with or without a goal).
            if (f.opportunityCosts.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text('Opportunity cost', style: tt.labelLarge),
              const SizedBox(height: 4),
              for (final o in f.opportunityCosts)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text('• '),
                    Expanded(child: Text(o.summary)),
                  ]),
                ),
            ],

            // Story.
            if (f.story != null) ...[
              const SizedBox(height: 12),
              Text(f.story!.beginning),
              if (f.story!.middle.isNotEmpty) ...[const SizedBox(height: 4), Text(f.story!.middle)],
              if (f.story!.end.isNotEmpty) ...[const SizedBox(height: 4), Text(f.story!.end)],
            ],

            // Level 3 — evidence behind a disclosure.
            if (f.evidence.isNotEmpty) _EvidenceExpander(f.evidence),

            // Timeline candidate.
            if (f.timelineCandidates.isNotEmpty) ...[
              const SizedBox(height: 8),
              for (final t in f.timelineCandidates)
                Row(children: [
                  Icon(Icons.event_outlined, size: 14, color: cs.outline),
                  const SizedBox(width: 4),
                  Expanded(child: Text('${t.label} — ${_date(t.date)}', style: tt.bodySmall)),
                ]),
            ],

            // What-if levers (tap → recalculate).
            if (f.levers.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text('Try a what-if', style: tt.labelLarge),
              const SizedBox(height: 6),
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final lv in f.levers)
                  ActionChip(label: Text(lv.label), onPressed: () => onLever(lv.ref)),
              ]),
            ],

            // Follow-ups + explain.
            if (f.explainRef != null || f.followUps.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(spacing: 8, runSpacing: 8, children: [
                if (f.explainRef != null)
                  ActionChip(label: const Text('Show evidence'), onPressed: () => onExplain(f.explainRef!)),
                for (final o in f.followUps) ActionChip(label: Text(o.label), onPressed: () => onTap(o.message)),
              ]),
            ],
          ],
        ),
      ),
    );
  }
}

class _PathTile extends StatelessWidget {
  const _PathTile(this.p, {required this.currency, required this.dateOf});
  final ScenarioPath p;
  final String currency;
  final String Function(String?) dateOf;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(color: cs.surfaceContainerHighest, borderRadius: BorderRadius.circular(10)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Text(p.label, style: const TextStyle(fontWeight: FontWeight.w600)),
            Text(p.eta != null ? dateOf(p.eta) : 'not reachable',
                style: TextStyle(fontWeight: FontWeight.w700, color: cs.primary)),
          ]),
          const SizedBox(height: 2),
          Text('${formatMoney(p.monthlyRate, currency)}/month', style: Theme.of(context).textTheme.bodySmall),
          if (p.narrative.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(p.narrative, style: Theme.of(context).textTheme.bodySmall),
          ],
        ],
      ),
    );
  }
}

class _EvidenceExpander extends StatelessWidget {
  const _EvidenceExpander(this.evidence);
  final List<EvidenceItem> evidence;

  @override
  Widget build(BuildContext context) {
    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        childrenPadding: const EdgeInsets.only(bottom: 8),
        title: const Text('Show evidence', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
        children: [
          for (final it in evidence)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                Expanded(child: Text(it.label + (it.when != null ? '  (${it.when})' : ''))),
                if (it.value != null) Text(it.value!, style: const TextStyle(fontWeight: FontWeight.w600)),
              ]),
            ),
        ],
      ),
    );
  }
}
