import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/format/dates.dart';
import '../../core/format/money.dart';
import '../calendar/calendar_models.dart';
import '../calendar/calendar_repository.dart';
import '../capture/scan_receipt_button.dart';

/// Composes a human, deterministic line about a day from its real numbers.
/// (Richer personalized commentary connects to the advisor engine in Sprint 4.)
String dayCommentary(DayDetail d, DateTime today) {
  final cur = d.currency;
  final isFuture = d.date.isAfter(DateTime(today.year, today.month, today.day));
  final spent = double.tryParse(d.spent) ?? 0;
  final budget = double.tryParse(d.effectiveBudget ?? '') ;

  if (isFuture) {
    if (d.events.isNotEmpty) {
      return '${formatDate(d.date)}: ${d.events.length} planned — ${d.events.first.title}.';
    }
    return 'Nothing planned for ${formatDate(d.date)} yet. Add an event or a budget to get ahead.';
  }
  switch (d.classification) {
    case 'over':
      final over = (budget != null) ? formatMoney((spent - budget).toString(), cur) : null;
      return over != null
          ? "You went over budget on ${formatDate(d.date)} by $over. Tap a reason so I can learn what happened."
          : 'You spent ${formatMoney(d.spent, cur)} on ${formatDate(d.date)}.';
    case 'saved':
      final saved = (budget != null) ? formatMoney((budget - spent).toString(), cur) : null;
      return saved != null
          ? 'Nice — you saved $saved on ${formatDate(d.date)}. 👑'
          : 'You stayed light on ${formatDate(d.date)}.';
    case 'within':
      return 'Right on budget for ${formatDate(d.date)}.';
    default:
      if (spent == 0 && d.income == '0' && d.events.isEmpty) {
        return 'Nothing recorded on ${formatDate(d.date)} yet. Add an expense, income, or event.';
      }
      return 'On ${formatDate(d.date)} you spent ${formatMoney(d.spent, cur)}.';
  }
}

class DateDetailsScreen extends ConsumerWidget {
  const DateDetailsScreen({super.key, required this.date});
  final DateTime date;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final iso = ymd(date);
    final async = ref.watch(dayDetailProvider(iso));
    final today = DateTime.now();

    return CompanionScaffold(
      title: formatDate(date),
      commentary: async.valueOrNull != null ? dayCommentary(async.value!, today) : null,
      mood: moodFromClassification(async.valueOrNull?.classification),
      child: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => _Error(
          message: e is AppError ? e.message : 'Couldn’t load this day.',
          onRetry: () => ref.invalidate(dayDetailProvider(iso)),
        ),
        data: (d) => ListView(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 32),
          children: [
            _Summary(d),
            if (d.classification == 'over' && (d.overspendReason?.isEmpty ?? true))
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
                child: Text('Tip: note why this day went over in Plan Today so the advisor can learn.',
                    style: Theme.of(context).textTheme.bodySmall),
              ),
            if ((d.overspendReason?.isNotEmpty ?? false))
              Card(
                color: Theme.of(context).colorScheme.errorContainer,
                child: ListTile(
                  leading: const Icon(Icons.sticky_note_2_outlined),
                  title: Text('Why it went over: ${d.overspendReason}'),
                ),
              ),
            _AddBar(iso: iso),
            _Section(title: 'Expenses', lines: d.expenses, icon: Icons.south_west, credit: false),
            _Section(title: 'Income', lines: d.incomes, icon: Icons.north_east, credit: true),
            _Section(title: 'Planned events', lines: d.events, icon: Icons.event, credit: null),
          ],
        ),
      ),
    );
  }
}

class _Summary extends StatelessWidget {
  const _Summary(this.d);
  final DayDetail d;
  @override
  Widget build(BuildContext context) {
    final chips = <Widget>[
      _chip(context, 'Spent', formatMoney(d.spent, d.currency)),
      if (d.income != '0') _chip(context, 'Income', formatMoney(d.income, d.currency)),
      if (d.effectiveBudget != null) _chip(context, 'Budget', formatMoney(d.effectiveBudget, d.currency)),
      if (d.remaining != null) _chip(context, 'Remaining', formatMoney(d.remaining, d.currency)),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Wrap(spacing: 8, runSpacing: 8, children: chips),
      ),
    );
  }

  Widget _chip(BuildContext c, String label, String value) =>
      Chip(label: Text('$label  $value'), visualDensity: VisualDensity.compact);
}

class _AddBar extends StatelessWidget {
  const _AddBar({required this.iso});
  final String iso;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Wrap(
        spacing: 8,
        children: [
          OutlinedButton.icon(
            onPressed: () => context.go('/date/$iso/add-expense'),
            icon: const Icon(Icons.remove),
            label: const Text('Expense'),
          ),
          const ScanReceiptButton(),
          OutlinedButton.icon(
            onPressed: () => context.go('/date/$iso/add-income'),
            icon: const Icon(Icons.add),
            label: const Text('Income'),
          ),
          OutlinedButton.icon(
            onPressed: () => context.go('/date/$iso/add-event'),
            icon: const Icon(Icons.event),
            label: const Text('Event'),
          ),
          OutlinedButton.icon(
            onPressed: () => context.go('/date/$iso/add-lent'),
            icon: const Icon(Icons.volunteer_activism),
            label: const Text('Lent'),
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.lines, required this.icon, required this.credit});
  final String title;
  final List<DayLine> lines;
  final IconData icon;
  final bool? credit;
  @override
  Widget build(BuildContext context) {
    if (lines.isEmpty) return const SizedBox.shrink();
    final color = credit == null
        ? Theme.of(context).colorScheme.primary
        : (credit! ? Colors.green.shade700 : Theme.of(context).colorScheme.error);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 12, 4, 4),
          child: Text(title, style: Theme.of(context).textTheme.titleSmall),
        ),
        Card(
          child: Column(
            children: [
              for (var i = 0; i < lines.length; i++) ...[
                if (i > 0) const Divider(height: 1),
                ListTile(
                  leading: Icon(icon, color: color),
                  title: Text(lines[i].title),
                  subtitle: lines[i].tag != null ? Text(lines[i].tag!) : null,
                  // A note/reminder event has no money — show no amount for it.
                  trailing: (double.tryParse(lines[i].amount) ?? 0) == 0
                      ? null
                      : Text(formatMoney(lines[i].amount, lines[i].currency),
                          style: TextStyle(color: color, fontWeight: FontWeight.w600)),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _Error extends StatelessWidget {
  const _Error({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(message),
            const SizedBox(height: 12),
            FilledButton.tonal(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      );
}
