import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/companion/companion_orb.dart';
import '../../core/format/dates.dart';
import '../../core/theme/glass.dart';
import 'payable_repository.dart';

/// Advary's repayment conversation: pick when + how, and it works out — via the
/// affordability engine — whether that's doable, the monthly pace, and (when
/// it's tight) realistic later dates. The "understands my money" moment.
class RepaymentPlanScreen extends ConsumerStatefulWidget {
  const RepaymentPlanScreen({super.key, required this.payableId});
  final String payableId;

  @override
  ConsumerState<RepaymentPlanScreen> createState() => _RepaymentPlanScreenState();
}

class _RepaymentPlanScreenState extends ConsumerState<RepaymentPlanScreen> {
  DateTime? _date;
  String _preference = 'auto';
  RepaymentPlan? _plan;
  bool _busy = false;
  String? _error;

  static const _prefs = <({String value, String label})>[
    (value: 'all_at_once', label: 'All at once'),
    (value: 'gradual', label: 'Gradually'),
    (value: 'auto', label: 'Let Advary decide'),
  ];

  DateTime _addMonths(DateTime d, int n) {
    final m = d.month - 1 + n;
    final y = d.year + m ~/ 12;
    final mm = m % 12 + 1;
    final lastDay = DateTime(y, mm + 1, 0).day;
    return DateTime(y, mm, d.day > lastDay ? lastDay : d.day);
  }

  Future<void> _pickDate() async {
    final base = _date ?? DateTime.now().add(const Duration(days: 30));
    final picked = await showDatePicker(
      context: context, initialDate: base, firstDate: DateTime.now(), lastDate: DateTime(2100));
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _planIt() async {
    if (_date == null) return;
    setState(() { _busy = true; _error = null; });
    try {
      final plan = await ref.read(payableRepositoryProvider)
          .repaymentPlan(widget.payableId, targetDate: _date!, preference: _preference);
      if (!mounted) return;
      setState(() { _plan = plan; _busy = false; });
    } on AppError catch (e) {
      if (!mounted) return;
      setState(() { _busy = false; _error = e.message; });
    } catch (_) {
      if (!mounted) return;
      setState(() { _busy = false; _error = 'Could not work that out. Please try again.'; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    final summary = ref.watch(payableSummaryProvider(widget.payableId));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Repayment plan'),
        leading: IconButton(icon: const Icon(Icons.close), onPressed: () => context.go('/home')),
      ),
      body: summary.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => Center(child: Text('Could not load this debt.', style: tt.bodyMedium)),
        data: (p) {
          // Default the date to the due date (or ~a month out) the first time.
          _date ??= p.dueDate ?? DateTime.now().add(const Duration(days: 30));
          final dueOr = p.dueDate ?? DateTime.now().add(const Duration(days: 30));
          final dateChoices = [dueOr, _addMonths(dueOr, 1), _addMonths(dueOr, 2)];

          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
            children: [
              Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const CompanionOrb(state: OrbState.idle, size: 56),
                const SizedBox(width: 12),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text('You borrowed ${p.currency} ${p.amount.replaceAll(RegExp(r"\.0+$"), "")} from ${p.who}. Let’s plan paying it back.',
                        style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w600, height: 1.3)),
                  ),
                ),
              ]),
              const SizedBox(height: 20),
              Text('When would you like to repay it?', style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final d in dateChoices)
                  ChoiceChip(
                    label: Text(formatDate(d)),
                    selected: _sameDay(_date, d),
                    onSelected: (_) => setState(() { _date = d; _plan = null; }),
                  ),
                ActionChip(avatar: const Icon(Icons.edit_calendar, size: 18), label: const Text('Pick a date'), onPressed: _pickDate),
              ]),
              const SizedBox(height: 20),
              Text('How would you like to pay?', style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final o in _prefs)
                  ChoiceChip(
                    label: Text(o.label),
                    selected: _preference == o.value,
                    onSelected: (_) => setState(() { _preference = o.value; _plan = null; }),
                  ),
              ]),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: _busy ? null : _planIt,
                icon: _busy
                    ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.auto_awesome, size: 18),
                label: Text(_busy ? 'Working it out…' : 'Work out a plan'),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: tt.bodySmall?.copyWith(color: cs.error)),
              ],
              if (_plan != null) ...[
                const SizedBox(height: 20),
                _PlanCard(plan: _plan!, onPickAlt: (d) => setState(() { _date = d; _plan = null; })),
              ],
            ],
          );
        },
      ),
    );
  }

  static bool _sameDay(DateTime? a, DateTime b) =>
      a != null && a.year == b.year && a.month == b.month && a.day == b.day;
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({required this.plan, required this.onPickAlt});
  final RepaymentPlan plan;
  final void Function(DateTime) onPickAlt;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    final ok = plan.feasible;
    final accent = ok ? const Color(0xFF43E08A) : const Color(0xFFFFB300);
    return GlassCard(
      gradient: LinearGradient(
        begin: Alignment.topLeft, end: Alignment.bottomRight,
        colors: [accent.withValues(alpha: 0.16), Colors.black.withValues(alpha: 0.28)]),
      borderColor: accent.withValues(alpha: 0.30),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(ok ? Icons.check_circle_outline : Icons.info_outline, color: accent, size: 22),
            const SizedBox(width: 8),
            Expanded(child: Text(plan.headline, style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w700, height: 1.3))),
          ]),
          const SizedBox(height: 10),
          for (final line in plan.impact)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text('•  $line', style: tt.bodyMedium?.copyWith(color: cs.onSurfaceVariant, height: 1.3)),
            ),
          if (plan.alternatives.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text('Dates that work better:', style: tt.labelLarge?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final a in plan.alternatives)
                if (a.date != null)
                  ActionChip(label: Text(a.label), onPressed: () => onPickAlt(a.date!))
                else
                  Chip(label: Text(a.label), backgroundColor: Colors.white.withValues(alpha: 0.05)),
            ]),
          ],
          const SizedBox(height: 14),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton.tonal(
              onPressed: () => context.go('/home'),
              child: const Text('Sounds good'),
            ),
          ),
        ],
      ),
    );
  }
}
