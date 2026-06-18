import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/format/money.dart';
import '../../core/settings/settings_repository.dart';
import '../../core/widgets/otherable_chips.dart';
import '../calendar/calendar_repository.dart';
import '../home/dashboard_repository.dart';
import '../settings/settings_screen.dart';
import 'budget_repository.dart';
import 'budget_setup_models.dart';

const _draftKey = 'budget_setup_draft';

// Steps (step 2 = family detail, skipped unless income source is Family support).
const _intro = 0, _source = 1, _family = 2, _income = 3, _commitments = 4, _goals = 5, _review = 6;

class BudgetSetupScreen extends ConsumerStatefulWidget {
  const BudgetSetupScreen({super.key});

  @override
  ConsumerState<BudgetSetupScreen> createState() => _BudgetSetupScreenState();
}

class _BudgetSetupScreenState extends ConsumerState<BudgetSetupScreen> {
  final _storage = const FlutterSecureStorage();
  BudgetDraft _d = BudgetDraft();
  bool _loading = true;
  bool _resumeOffer = false;
  bool _busy = false;
  BudgetSummary? _result;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final saved = await _storage.read(key: _draftKey);
    if (saved != null) {
      try {
        _d = BudgetDraft.decode(saved);
        _resumeOffer = true;
      } catch (_) {
        _d = BudgetDraft();
      }
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _persist() async => _storage.write(key: _draftKey, value: _d.encode());
  Future<void> _clearDraft() async => _storage.delete(key: _draftKey);

  void _go(int step) {
    setState(() => _d.step = step);
    _persist();
  }

  void _next() {
    var s = _d.step;
    s = s + 1;
    if (s == _family && _d.incomeSource != 'Family support') s++; // skip family detail
    _go(s);
  }

  void _back() {
    var s = _d.step - 1;
    if (s == _family && _d.incomeSource != 'Family support') s--;
    if (s < _intro) s = _intro;
    _go(s);
  }

  String _commentary() {
    switch (_d.step) {
      case _intro:
        return "Let's understand your financial life a little — it helps me give advice that fits you.";
      case _source:
        return 'Where does most of your money come from?';
      case _family:
        return 'Who usually helps you out?';
      case _income:
        return 'Roughly how much comes in each month?';
      case _commitments:
        return 'Anything that regularly takes money each month? Add what applies.';
      case _goals:
        return 'Saving toward anything? You can skip this for now.';
      default:
        return "Here's the budget I worked out — and how I got there.";
    }
  }

  Future<void> _finish() async {
    final currency = ref.read(userSettingsProvider).valueOrNull?.baseCurrency;
    if (currency == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Couldn’t read your base currency. Try again.')));
      return;
    }
    setState(() => _busy = true);
    final repo = ref.read(budgetRepositoryProvider);
    try {
      if (_d.incomeSource == 'Family support') {
        for (final who in _d.familyWho) {
          await repo.createPerson(name: who, relationshipType: 'family', reason: _d.incomeWhy);
        }
      }
      if (_d.incomeAmount.trim().isNotEmpty) {
        await repo.createIncomeSource(
          label: _d.incomeSource ?? 'Income',
          sourceType: mapIncomeSourceType(_d.incomeSource ?? 'Other'),
          amount: _d.incomeAmount.trim(),
          currency: currency,
          reason: _d.incomeWhy,
        );
      }
      for (final c in _d.commitments) {
        await repo.createRecurringRule(
          ruleType: mapCommitmentRuleType(c.type),
          label: c.label,
          amount: c.amount,
          currency: currency,
          recurrenceDay: c.day,
          startDate: DateTime.now(),
          reason: c.why,
        );
      }
      for (final g in _d.goals) {
        await repo.createSavingsGoal(name: g.name, amount: g.amount, currency: currency, reason: g.why);
      }
      final summary = await repo.apply();
      await _clearDraft();
      if (!mounted) return;
      ref.invalidate(monthViewProvider);
      ref.invalidate(dailyBriefProvider);
      setState(() {
        _result = summary;
        _busy = false;
        _d.step = _review;
      });
    } on AppError catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const CompanionScaffold(title: 'Budget Setup', child: Center(child: CircularProgressIndicator()));
    }
    return CompanionScaffold(
      title: 'Budget Setup',
      commentary: _commentary(),
      mood: _d.step == _review ? CompanionMood.happy : CompanionMood.neutral,
      child: AbsorbPointer(
        absorbing: _busy,
        child: _resumeOffer ? _resumeCard() : _stepBody(),
      ),
    );
  }

  Widget _resumeCard() => ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Last time we were setting up your financial profile.'),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: FilledButton(
                          onPressed: () => setState(() => _resumeOffer = false),
                          child: const Text('Continue'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      TextButton(
                        onPressed: () {
                          _clearDraft();
                          setState(() {
                            _d = BudgetDraft();
                            _resumeOffer = false;
                          });
                        },
                        child: const Text('Start over'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      );

  Widget _stepBody() {
    switch (_d.step) {
      case _intro:
        final currency = ref.watch(userSettingsProvider).valueOrNull?.baseCurrency ?? 'INR';
        return _pad([
          const Text('A few quick questions — no spreadsheets, I promise.'),
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              leading: const Icon(Icons.payments_outlined),
              title: const Text('Currency you use'),
              subtitle: const Text('I’ll use this everywhere'),
              trailing: Text(currency, style: Theme.of(context).textTheme.titleMedium),
              onTap: () => changePreferredCurrency(context, ref),
            ),
          ),
          const SizedBox(height: 20),
          FilledButton(onPressed: _next, child: const Text("Let's start")),
        ]);
      case _source:
        final sourceSet = _d.incomeSource != null && _d.incomeSource!.isNotEmpty;
        return _pad([
          OtherableChips(
            options: incomeSourceOptions,
            initialValue: _d.incomeSource,
            onChanged: (value, _) => setState(() => _d.incomeSource = value),
          ),
          const SizedBox(height: 20),
          _nextRow(enabled: sourceSet),
        ]);
      case _family:
        return _pad([
          _multiChips(familyWhoOptions, _d.familyWho),
          const SizedBox(height: 20),
          _nextRow(enabled: _d.familyWho.isNotEmpty),
        ]);
      case _income:
        return _pad([
          TextField(
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
            decoration: const InputDecoration(labelText: 'Monthly amount'),
            controller: TextEditingController(text: _d.incomeAmount)
              ..selection = TextSelection.collapsed(offset: _d.incomeAmount.length),
            onChanged: (v) => _d.incomeAmount = v,
          ),
          const SizedBox(height: 16),
          const Text('Why does this income matter? (optional)'),
          const SizedBox(height: 8),
          OtherableChips(
            options: incomeWhyOptions,
            initialValue: _d.incomeWhy,
            onChanged: (value, _) => setState(() => _d.incomeWhy = value),
          ),
          const SizedBox(height: 20),
          _nextRow(enabled: double.tryParse(_d.incomeAmount.trim()) != null),
        ]);
      case _commitments:
        return _pad([
          ..._d.commitments.asMap().entries.map((e) => Card(
                child: ListTile(
                  title: Text('${e.value.type} · ${e.value.label}'),
                  subtitle: Text('day ${e.value.day}'),
                  trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                    Text(e.value.amount),
                    IconButton(
                      icon: const Icon(Icons.delete_outline),
                      onPressed: () => setState(() => _d.commitments.removeAt(e.key)),
                    ),
                  ]),
                ),
              )),
          OutlinedButton.icon(
            onPressed: _addCommitment,
            icon: const Icon(Icons.add),
            label: const Text('Add a recurring expense'),
          ),
          const SizedBox(height: 20),
          _nextRow(enabled: true, label: 'Next'),
        ]);
      case _goals:
        return _pad([
          ..._d.goals.asMap().entries.map((e) => Card(
                child: ListTile(
                  title: Text(e.value.name),
                  subtitle: e.value.why != null ? Text(e.value.why!) : null,
                  trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                    Text(e.value.amount),
                    IconButton(
                      icon: const Icon(Icons.delete_outline),
                      onPressed: () => setState(() => _d.goals.removeAt(e.key)),
                    ),
                  ]),
                ),
              )),
          OutlinedButton.icon(onPressed: _addGoal, icon: const Icon(Icons.add), label: const Text('Add a savings goal')),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _busy ? null : _finish,
            child: _busy
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Generate my budget'),
          ),
        ]);
      default:
        return _reviewBody();
    }
  }

  Widget _reviewBody() {
    final s = _result;
    if (s == null) return _pad([const Text('Budget ready.')]);
    Widget row(String label, String value) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [Text(label), Text(formatMoney(value, s.currency), style: const TextStyle(fontWeight: FontWeight.w600))],
          ),
        );
    return _pad([
      Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(children: [
            row('Monthly budget', s.monthlyDiscretionary),
            row('Weekly budget', s.weekly),
            row('Daily budget', s.daily),
          ]),
        ),
      ),
      const SizedBox(height: 16),
      Text('How I worked this out', style: Theme.of(context).textTheme.titleSmall),
      const SizedBox(height: 8),
      Text('Income ${formatMoney(s.monthlyIncome, s.currency)} '
          '− commitments ${formatMoney(s.monthlyCommitments, s.currency)} '
          '− savings ${formatMoney(s.monthlyGoals, s.currency)} '
          '= ${formatMoney(s.monthlyDiscretionary, s.currency)} to spend each month. '
          'Weekly is that ÷ 4.33; daily is the monthly amount ÷ days in the month. '
          'Your calendar now uses this as your daily budget.'),
      const SizedBox(height: 20),
      FilledButton(onPressed: () => context.go('/home'), child: const Text('Done')),
    ]);
  }

  Future<void> _addCommitment() async {
    final c = await showDialog<Commitment>(context: context, builder: (_) => const _CommitmentDialog());
    if (c != null) setState(() => _d.commitments.add(c));
    _persist();
  }

  Future<void> _addGoal() async {
    final g = await showDialog<GoalDraft>(context: context, builder: (_) => const _GoalDialog());
    if (g != null) setState(() => _d.goals.add(g));
    _persist();
  }

  // --- shared bits ---
  Widget _pad(List<Widget> children) => ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: children,
      );

  // Buttons are themed full-width (infinite min-width), so they must be given a
  // bounded width via Expanded when placed in a Row.
  Widget _nextRow({required bool enabled, String label = 'Next'}) => Row(
        children: [
          if (_d.step > _source) ...[
            Expanded(child: OutlinedButton(onPressed: _back, child: const Text('Back'))),
            const SizedBox(width: 12),
          ],
          Expanded(child: FilledButton(onPressed: enabled ? _next : null, child: Text(label))),
        ],
      );

  Widget _multiChips(List<String> options, List<String> selected) => Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final o in options)
            FilterChip(
              label: Text(o),
              selected: selected.contains(o),
              onSelected: (on) => setState(() => on ? selected.add(o) : selected.remove(o)),
            ),
        ],
      );
}

class _CommitmentDialog extends StatefulWidget {
  const _CommitmentDialog();
  @override
  State<_CommitmentDialog> createState() => _CommitmentDialogState();
}

class _CommitmentDialogState extends State<_CommitmentDialog> {
  String _type = commitmentTypeOptions.first;
  final _label = TextEditingController();
  final _amount = TextEditingController();
  final _day = TextEditingController(text: '1');

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Recurring expense'),
      content: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          DropdownButtonFormField<String>(
            initialValue: _type,
            decoration: const InputDecoration(labelText: 'Type'),
            items: [for (final t in commitmentTypeOptions) DropdownMenuItem(value: t, child: Text(t))],
            onChanged: (v) => setState(() => _type = v ?? _type),
          ),
          TextField(controller: _label, decoration: const InputDecoration(labelText: 'Name (e.g. Netflix)')),
          TextField(
            controller: _amount,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
            decoration: const InputDecoration(labelText: 'Monthly amount'),
          ),
          TextField(
            controller: _day,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            decoration: const InputDecoration(labelText: 'Day of month (1-31)'),
          ),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(
          onPressed: () {
            final amt = double.tryParse(_amount.text.trim());
            final day = int.tryParse(_day.text.trim()) ?? 1;
            if (amt == null || amt <= 0 || _label.text.trim().isEmpty) return;
            Navigator.pop(
              context,
              Commitment(
                type: _type,
                label: _label.text.trim(),
                amount: _amount.text.trim(),
                day: day.clamp(1, 31),
              ),
            );
          },
          child: const Text('Add'),
        ),
      ],
    );
  }
}

class _GoalDialog extends StatefulWidget {
  const _GoalDialog();
  @override
  State<_GoalDialog> createState() => _GoalDialogState();
}

class _GoalDialogState extends State<_GoalDialog> {
  final _name = TextEditingController();
  final _amount = TextEditingController();
  String? _why;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Savings goal'),
      content: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: _name, decoration: const InputDecoration(labelText: 'Goal (e.g. Japan fund)')),
          TextField(
            controller: _amount,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
            decoration: const InputDecoration(labelText: 'Monthly amount'),
          ),
          const SizedBox(height: 12),
          const Align(alignment: Alignment.centerLeft, child: Text('Why is this important?')),
          const SizedBox(height: 6),
          OtherableChips(
            options: goalWhyOptions,
            initialValue: _why,
            onChanged: (value, _) => setState(() => _why = value),
          ),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(
          onPressed: () {
            final amt = double.tryParse(_amount.text.trim());
            if (amt == null || amt <= 0 || _name.text.trim().isEmpty) return;
            Navigator.pop(context, GoalDraft(name: _name.text.trim(), amount: _amount.text.trim(), why: _why));
          },
          child: const Text('Add'),
        ),
      ],
    );
  }
}
