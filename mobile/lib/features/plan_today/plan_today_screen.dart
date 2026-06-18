import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/format/dates.dart';
import '../../core/format/money.dart';
import '../calendar/calendar_models.dart';
import '../calendar/calendar_repository.dart';
import 'daily_plan_repository.dart';

const _overspendReasons = [
  'Unplanned purchase',
  'Emergency',
  'Social plans',
  'Forgot to track',
  'Other',
];

class PlanTodayScreen extends ConsumerWidget {
  const PlanTodayScreen({super.key});

  DateTime get _today => DateTime.now();

  void _refresh(WidgetRef ref, String iso) {
    ref.invalidate(dayDetailProvider(iso));
    ref.invalidate(monthViewProvider);
  }

  Future<void> _setBudget(BuildContext context, WidgetRef ref, {bool override = false}) async {
    final iso = ymd(_today);
    final amount = await _promptAmount(context, override: override);
    if (amount == null) return;
    try {
      await ref.read(dailyPlanRepositoryProvider).setBudget(_today, amount, override: override);
      _refresh(ref, iso);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Budget set')));
      }
    } on ValidationError catch (e) {
      // Locked after spending began — confirm an override.
      if (!context.mounted) return;
      final ok = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Budget locked'),
          content: Text('${e.message}\n\nChange it anyway?'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Keep it')),
            FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Change anyway')),
          ],
        ),
      );
      if (ok == true && context.mounted) await _setBudget(context, ref, override: true);
    } on AppError catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  Future<String?> _promptAmount(BuildContext context, {required bool override}) {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text(override ? 'New daily budget' : "Today's budget"),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
          decoration: const InputDecoration(labelText: 'Amount'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              final v = ctrl.text.trim();
              final n = double.tryParse(v);
              Navigator.pop(c, (n != null && n > 0) ? v : null);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  Future<void> _addReason(BuildContext context, WidgetRef ref) async {
    final iso = ymd(_today);
    final reason = await showDialog<String>(
      context: context,
      builder: (c) => SimpleDialog(
        title: const Text('What contributed most to the extra spending?'),
        children: [
          for (final r in _overspendReasons)
            SimpleDialogOption(onPressed: () => Navigator.pop(c, r), child: Text(r)),
        ],
      ),
    );
    if (reason == null) return;
    try {
      await ref.read(dailyPlanRepositoryProvider).setOverspendReason(_today, reason);
      _refresh(ref, iso);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Noted — thanks for sharing')));
      }
    } on AppError catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  String _commentary(DayDetail? d) {
    if (d == null) return 'Let’s plan today.';
    final budget = double.tryParse(d.effectiveBudget ?? '');
    if (budget == null) return 'Set a daily budget and I’ll track your spending against it.';
    if (d.classification == 'over') {
      return "You're over today's budget. Spending still records — tell me why so I can help next time.";
    }
    final remaining = formatMoney(d.remaining, d.currency);
    return "You've spent ${formatMoney(d.spent, d.currency)} of ${formatMoney(d.effectiveBudget, d.currency)} — $remaining left today.";
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final iso = ymd(_today);
    final async = ref.watch(dayDetailProvider(iso));

    return CompanionScaffold(
      title: 'Plan Today',
      commentary: _commentary(async.valueOrNull),
      mood: moodFromClassification(async.valueOrNull?.classification),
      child: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(e is AppError ? e.message : 'Couldn’t load today.'),
            const SizedBox(height: 12),
            FilledButton.tonal(onPressed: () => ref.invalidate(dayDetailProvider(iso)), child: const Text('Retry')),
          ]),
        ),
        data: (d) => ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            _BudgetCard(d),
            const SizedBox(height: 12),
            Wrap(spacing: 8, runSpacing: 8, children: [
              FilledButton.tonalIcon(
                onPressed: () => _setBudget(context, ref),
                icon: const Icon(Icons.tune),
                label: Text(d.effectiveBudget == null ? 'Set budget' : 'Adjust budget'),
              ),
              if (d.classification == 'over' && (d.overspendReason?.isEmpty ?? true))
                FilledButton.tonalIcon(
                  onPressed: () => _addReason(context, ref),
                  icon: const Icon(Icons.edit_note),
                  label: const Text('Add overspend reason'),
                ),
            ]),
            const SizedBox(height: 8),
            Wrap(spacing: 8, children: [
              OutlinedButton.icon(
                onPressed: () => context.go('/date/$iso/add-expense'),
                icon: const Icon(Icons.remove),
                label: const Text('Add expense'),
              ),
              OutlinedButton.icon(
                onPressed: () => context.go('/date/$iso/add-income'),
                icon: const Icon(Icons.add),
                label: const Text('Add income'),
              ),
            ]),
            if (d.overspendReason?.isNotEmpty ?? false) ...[
              const SizedBox(height: 12),
              Card(
                color: Theme.of(context).colorScheme.errorContainer,
                child: ListTile(
                  leading: const Icon(Icons.sticky_note_2_outlined),
                  title: Text('Overspend reason: ${d.overspendReason}'),
                ),
              ),
            ],
            const SizedBox(height: 8),
            Center(
              child: TextButton(
                onPressed: () => context.go('/date/$iso'),
                child: const Text("See today's details"),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BudgetCard extends StatelessWidget {
  const _BudgetCard(this.d);
  final DayDetail d;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final budget = double.tryParse(d.effectiveBudget ?? '');
    final spent = double.tryParse(d.spent) ?? 0;
    final ratio = (budget == null || budget == 0) ? 0.0 : (spent / budget).clamp(0.0, 1.0);
    final over = budget != null && spent > budget;
    final near = budget != null && !over && spent >= 0.9 * budget;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("Today's budget", style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Spent ${formatMoney(d.spent, d.currency)}'),
                Text(budget == null ? 'No budget set' : 'of ${formatMoney(d.effectiveBudget, d.currency)}'),
              ],
            ),
            const SizedBox(height: 8),
            if (budget != null)
              LinearProgressIndicator(
                value: over ? 1.0 : ratio,
                minHeight: 8,
                color: over ? cs.error : (near ? Colors.orange : cs.primary),
                backgroundColor: cs.surfaceContainerHighest,
              ),
            const SizedBox(height: 10),
            if (over)
              Text('⚠️ Over budget — by ${formatMoney((spent - budget).toString(), d.currency)}. '
                  'Keep recording so we can see where it went.',
                  style: TextStyle(color: cs.error))
            else if (near)
              Text('You’re at 90% of today’s budget — ${formatMoney(d.remaining, d.currency)} left.',
                  style: const TextStyle(color: Colors.orange))
            else if (budget != null)
              Text('${formatMoney(d.remaining, d.currency)} remaining today.'),
          ],
        ),
      ),
    );
  }
}
