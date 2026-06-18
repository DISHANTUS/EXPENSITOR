import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/budget/budget_plan_repository.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/theme/glass.dart';

String _money(String cur, double v) => '$cur ${v.toStringAsFixed(0).replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},')}';

const _bandLabel = {
  'very_high': 'Very High', 'high': 'High', 'medium': 'Medium', 'low': 'Low', 'very_low': 'Very Low',
};
Color _bandColor(String band) => switch (band) {
      'very_high' => const Color(0xFF34D399),
      'high' => const Color(0xFF6EE7B7),
      'medium' => const Color(0xFFFBBF24),
      'low' => const Color(0xFFFB923C),
      _ => const Color(0xFFF87171),
    };

class PlanScreen extends ConsumerWidget {
  const PlanScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feas = ref.watch(feasibilityProvider);
    final recs = ref.watch(recommendationsProvider);
    return CompanionScaffold(
      title: 'Your Plan',
      commentary: 'Here’s your money reality — survival first, then savings.',
      child: feas.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => _PlanError(
          message: e is AppError ? e.message : 'I couldn’t load your plan just now.',
          onRetry: () {
            ref.invalidate(feasibilityProvider);
            ref.invalidate(recommendationsProvider);
          },
        ),
        data: (f) => ListView(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 32),
          children: [
            _probabilityHero(context, f),
            const SizedBox(height: 14),
            _waterfallCard(context, f),
            if (f.flags.isNotEmpty) ...[const SizedBox(height: 14), _flagsCard(context, f)],
            if (f.anomalies.isNotEmpty) ...[const SizedBox(height: 14), _anomaliesCard(context, f)],
            const SizedBox(height: 14),
            recs.when(
              loading: () => const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator())),
              error: (_, __) => const SizedBox.shrink(),
              data: (r) => _recommendations(context, r),
            ),
          ],
        ),
      ),
    );
  }

  Widget _probabilityHero(BuildContext context, Feasibility f) {
    final tt = Theme.of(context).textTheme;
    final band = f.goals.isNotEmpty ? f.goals.first.band : f.overallBand;
    final color = _bandColor(band);
    return GlassCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.insights_outlined, color: color),
          const SizedBox(width: 8),
          Text('Savings probability', style: tt.titleMedium),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(color: color.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(20)),
            child: Text(_bandLabel[band] ?? band, style: tt.labelLarge?.copyWith(color: color, fontWeight: FontWeight.w700)),
          ),
        ]),
        const SizedBox(height: 10),
        Text(f.summary, style: tt.bodyMedium),
        if (f.goals.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(f.goals.first.reason, style: tt.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
        ],
      ]),
    );
  }

  Widget _waterfallCard(BuildContext context, Feasibility f) {
    final tt = Theme.of(context).textTheme;
    // Only show rows that actually carry money (Income always shows). No ₹0 clutter.
    final steps = f.waterfall.where((s) => s.label == 'Income' || s.amount.abs() > 0.005).toList();
    return GlassCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Where your money goes', style: tt.titleMedium),
        const SizedBox(height: 4),
        Text('Living first, then goals, then lifestyle — backup money is whatever’s left.',
            style: tt.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
        const SizedBox(height: 12),
        for (final s in steps) _WaterfallRow(step: s, currency: f.currency),
        const Divider(height: 22),
        Row(children: [
          Expanded(child: Text('Comfortably free each month', style: tt.bodyMedium)),
          Text(_money(f.currency, f.comfortable),
              style: tt.titleMedium?.copyWith(color: Theme.of(context).colorScheme.primary, fontWeight: FontWeight.w700)),
        ]),
      ]),
    );
  }

  Widget _flagsCard(BuildContext context, Feasibility f) {
    final tt = Theme.of(context).textTheme;
    return GlassCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('What I notice', style: tt.titleMedium),
        const SizedBox(height: 8),
        for (final fl in f.flags)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(fl.severity == 'high' ? Icons.warning_amber_rounded : Icons.info_outline,
                  size: 18, color: fl.severity == 'high' ? const Color(0xFFFB923C) : Theme.of(context).colorScheme.onSurfaceVariant),
              const SizedBox(width: 8),
              Expanded(child: Text(fl.message, style: tt.bodyMedium)),
            ]),
          ),
      ]),
    );
  }

  Widget _anomaliesCard(BuildContext context, Feasibility f) {
    final tt = Theme.of(context).textTheme;
    return GlassCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        for (final a in f.anomalies) Text(a, style: tt.bodyMedium),
      ]),
    );
  }

  Widget _recommendations(BuildContext context, RecommendationSet r) {
    final tt = Theme.of(context).textTheme;
    if (r.onTrack) {
      return GlassCard(child: Row(children: [
        const Icon(Icons.check_circle_outline, color: Color(0xFF34D399)),
        const SizedBox(width: 10),
        Expanded(child: Text(r.summary, style: tt.bodyMedium)),
      ]));
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Ways to reach your goal', style: tt.titleLarge),
      const SizedBox(height: 4),
      Text(r.summary, style: tt.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
      const SizedBox(height: 12),
      for (final t in r.tiers) ...[_tierCard(context, r.currency, t), const SizedBox(height: 12)],
      if (r.whyNot != null) ...[
        GlassCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [const Icon(Icons.handshake_outlined, size: 18), const SizedBox(width: 8), Text('Honest take', style: tt.titleSmall)]),
          const SizedBox(height: 8),
          Text(r.whyNot!, style: tt.bodyMedium),
        ])),
        const SizedBox(height: 12),
      ],
      if (r.growIncome.isNotEmpty)
        GlassCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Or grow your income', style: tt.titleSmall),
          const SizedBox(height: 8),
          for (final g in r.growIncome)
            Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Icon(Icons.trending_up, size: 18, color: Color(0xFF34D399)),
              const SizedBox(width: 8),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(g.label, style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
                Text(g.detail, style: tt.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
              ])),
            ])),
        ])),
      if (r.protectionNote != null) ...[
        const SizedBox(height: 8),
        Text(r.protectionNote!, style: tt.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant, fontStyle: FontStyle.italic)),
      ],
    ]);
  }

  Widget _tierCard(BuildContext context, String cur, RecTier t) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    return GlassCard(
      borderColor: t.reaches ? const Color(0x6634D399) : null,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(t.title, style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
          const Spacer(),
          if (t.reaches) const Icon(Icons.check_circle, size: 18, color: Color(0xFF34D399)),
        ]),
        const SizedBox(height: 2),
        Row(children: [
          _pill(context, t.difficulty),
          const SizedBox(width: 6),
          _pill(context, '${t.confidence} confidence'),
          const Spacer(),
          Text('+${_money(cur, t.totalImpact)}/mo', style: tt.titleMedium?.copyWith(color: cs.primary, fontWeight: FontWeight.w700)),
        ]),
        const SizedBox(height: 10),
        for (final c in t.changes)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                if (c.protected) const Padding(padding: EdgeInsets.only(right: 6), child: Icon(Icons.shield_outlined, size: 16, color: Color(0xFFFB923C))),
                Expanded(child: Text(c.label, style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600))),
                Text('+${_money(cur, c.impact)}', style: tt.bodyMedium?.copyWith(color: const Color(0xFF34D399), fontWeight: FontWeight.w600)),
              ]),
              if (c.currentDaily != null)
                Text('${_money(cur, c.currentDaily!)}/day → ${_money(cur, c.suggestedDaily!)}/day',
                    style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant)),
              Text(c.reason, style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant)),
            ]),
          ),
      ]),
    );
  }

  Widget _pill(BuildContext context, String text) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
        decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(20)),
        child: Text(text, style: Theme.of(context).textTheme.labelSmall),
      );
}

class _PlanError extends StatelessWidget {
  const _PlanError({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(message, textAlign: TextAlign.center, style: tt.bodyMedium),
            const SizedBox(height: 12),
            FilledButton.tonal(onPressed: onRetry, child: const Text('Try again')),
          ],
        ),
      ),
    );
  }
}

/// One waterfall line. Lines with a breakdown (e.g. Essential living → food,
/// transport, phone) tap to expand, so every number is traceable to its source.
class _WaterfallRow extends StatefulWidget {
  const _WaterfallRow({required this.step, required this.currency});
  final WaterfallStep step;
  final String currency;

  @override
  State<_WaterfallRow> createState() => _WaterfallRowState();
}

class _WaterfallRowState extends State<_WaterfallRow> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    final s = widget.step;
    final isIncome = s.label == 'Income';
    final hasBreakdown = s.breakdown.isNotEmpty;

    final header = Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(children: [
        SizedBox(width: 18, child: Text(isIncome ? '↓' : '−', style: tt.bodyMedium?.copyWith(color: cs.primary))),
        Expanded(child: Text(s.label, style: tt.bodyMedium?.copyWith(fontWeight: isIncome ? FontWeight.w700 : FontWeight.w500))),
        Text(_money(widget.currency, s.amount), style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
        if (hasBreakdown)
          Padding(
            padding: const EdgeInsets.only(left: 6),
            child: AnimatedRotation(
              turns: _open ? 0.5 : 0,
              duration: const Duration(milliseconds: 200),
              child: Icon(Icons.expand_more, size: 18, color: cs.onSurfaceVariant),
            ),
          )
        else
          const SizedBox(width: 24),
      ]),
    );

    if (!hasBreakdown) return header;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(onTap: () => setState(() => _open = !_open), child: header),
        AnimatedCrossFade(
          firstChild: const SizedBox(width: double.infinity),
          secondChild: Padding(
            padding: const EdgeInsets.only(left: 18, bottom: 6),
            child: Column(children: [
              for (final b in s.breakdown)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Row(children: [
                    Expanded(child: Text(b.label, style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant))),
                    Text(_money(widget.currency, b.amount), style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant)),
                  ]),
                ),
            ]),
          ),
          crossFadeState: _open ? CrossFadeState.showSecond : CrossFadeState.showFirst,
          duration: const Duration(milliseconds: 200),
        ),
      ],
    );
  }
}
