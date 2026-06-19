import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/format/dates.dart';
import '../../core/settings/settings_repository.dart';
import '../budget_setup/budget_repository.dart';
import 'ledger_actions.dart';

/// Log money the user BORROWED. Not an accounting screen — just "who gave it" +
/// "how much", with the rest optional. The expected-return is the heart of it:
/// a hard debt and a no-strings favour from a best friend are very different.
class AddBorrowedScreen extends ConsumerStatefulWidget {
  const AddBorrowedScreen({super.key, required this.date});
  final DateTime date;

  @override
  ConsumerState<AddBorrowedScreen> createState() => _AddBorrowedScreenState();
}

class _AddBorrowedScreenState extends ConsumerState<AddBorrowedScreen> {
  final _formKey = GlobalKey<FormState>();
  final _person = TextEditingController();
  final _amount = TextEditingController();
  final _reason = TextEditingController();
  String _returnExpectation = 'required';
  String? _relationship; // captured now, used later by the relationship engine
  DateTime? _dueDate;
  bool _busy = false;

  static const _returnOptions = <({String value, String label})>[
    (value: 'required', label: 'Required — repay by a date'),
    (value: 'optional', label: 'Optional — repay when comfortable'),
    (value: 'whenever', label: 'Whenever possible — no rush'),
    (value: 'not_expected', label: 'Not expected — a gift / support'),
  ];
  static const _relationshipOptions = <String>[
    'Friend', 'Best friend', 'Family', 'Partner', 'Colleague', 'Other',
  ];

  @override
  void dispose() {
    _person.dispose();
    _amount.dispose();
    _reason.dispose();
    super.dispose();
  }

  bool get _needsDate => _returnExpectation == 'required' || _returnExpectation == 'optional';

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _dueDate ?? widget.date.add(const Duration(days: 30)),
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );
    if (picked != null) setState(() => _dueDate = picked);
  }

  Future<void> _save(String currency) async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      await ref.read(budgetRepositoryProvider).createBorrowedMoney(
            sourceName: _person.text.trim(),
            amount: _amount.text.trim(),
            currency: currency,
            returnExpectation: _returnExpectation,
            dueDate: _needsDate ? _dueDate : null,
            reason: _reason.text,
            relationshipContext: _relationship,
          );
      if (!mounted) return;
      completeLedgerWrite(context, ref, kind: 'borrowed');
    } on AppError catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not save. Please try again.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(userSettingsProvider);
    final currency = settings.valueOrNull?.baseCurrency;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Borrowed money'),
        leading: IconButton(icon: const Icon(Icons.close), onPressed: () => context.go('/date/${ymd(widget.date)}')),
      ),
      body: AbsorbPointer(
        absorbing: _busy,
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            children: [
              TextFormField(
                controller: _person,
                autofocus: true,
                decoration: const InputDecoration(labelText: 'Who gave you the money?'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Enter a name' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _amount,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
                decoration: InputDecoration(labelText: 'Amount', prefixText: currency == null ? null : '$currency  '),
                validator: (v) {
                  final n = double.tryParse((v ?? '').trim());
                  if (n == null || n <= 0) return 'Enter a valid amount';
                  return null;
                },
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                initialValue: _returnExpectation,
                decoration: const InputDecoration(labelText: 'Expected return'),
                items: [for (final o in _returnOptions) DropdownMenuItem(value: o.value, child: Text(o.label))],
                onChanged: (v) => setState(() => _returnExpectation = v ?? 'required'),
              ),
              if (_needsDate)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.event),
                  title: const Text('Repay by (optional)'),
                  subtitle: Text(_dueDate == null ? 'Not set' : formatDate(_dueDate!)),
                  trailing: Wrap(children: [
                    if (_dueDate != null)
                      IconButton(icon: const Icon(Icons.clear), onPressed: () => setState(() => _dueDate = null)),
                    TextButton(onPressed: _pickDate, child: Text(_dueDate == null ? 'Set' : 'Change')),
                  ]),
                ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String?>(
                initialValue: _relationship,
                decoration: const InputDecoration(labelText: 'Who are they to you? (optional)'),
                items: [
                  const DropdownMenuItem<String?>(value: null, child: Text('Prefer not to say')),
                  ...[for (final r in _relationshipOptions) DropdownMenuItem<String?>(value: r, child: Text(r))],
                ],
                onChanged: (v) => setState(() => _relationship = v),
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _reason,
                maxLength: 2000,
                decoration: const InputDecoration(labelText: 'What was it for? (optional)'),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: (_busy || currency == null) ? null : () => _save(currency),
                child: _busy
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Save'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
