import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/format/dates.dart';
import '../../core/settings/settings_repository.dart';
import '../../core/widgets/otherable_chips.dart';
import 'ledger_actions.dart';
import 'ledger_models.dart';
import 'ledger_repository.dart';

class AddIncomeScreen extends ConsumerStatefulWidget {
  const AddIncomeScreen({super.key, required this.date});

  final DateTime date;

  @override
  ConsumerState<AddIncomeScreen> createState() => _AddIncomeScreenState();
}

class _AddIncomeScreenState extends ConsumerState<AddIncomeScreen> {
  final _formKey = GlobalKey<FormState>();
  final _amount = TextEditingController();
  final _notes = TextEditingController();
  String _sourceType = incomeSourceOptions.first.value; // 'salary'
  String? _customSource; // set when the user picks "Other" and types their own
  late DateTime _date = widget.date;
  bool _busy = false;

  String? _composedDescription() {
    final parts = <String>[
      if (_customSource != null && _customSource!.isNotEmpty) _customSource!,
      if (_notes.text.trim().isNotEmpty) _notes.text.trim(),
    ];
    return parts.isEmpty ? null : parts.join(' — ');
  }

  @override
  void dispose() {
    _amount.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
    );
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _save(String currency) async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      await ref.read(ledgerRepositoryProvider).createIncome(
            sourceType: _sourceType,
            amount: _amount.text.trim(),
            currency: currency,
            date: _date,
            description: _composedDescription(),
          );
      if (!mounted) return;
      completeLedgerWrite(context, ref, kind: 'income');
    } on AppError catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Could not save. Please try again.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(userSettingsProvider);
    final currency = settings.valueOrNull?.baseCurrency;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Add income'),
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
                controller: _amount,
                autofocus: true,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
                decoration: InputDecoration(
                  labelText: 'Amount',
                  prefixText: currency == null ? null : '$currency  ',
                ),
                validator: _validateAmount,
              ),
              const SizedBox(height: 16),
              const Text('Source'),
              const SizedBox(height: 8),
              OtherableChips(
                options: incomeSourceOptions.map((o) => o.label).toList(),
                initialValue: incomeSourceLabel(_sourceType),
                onChanged: (value, isCustom) => setState(() {
                  if (isCustom) {
                    _customSource = value;
                    _sourceType = 'other';
                  } else {
                    _customSource = null;
                    _sourceType = incomeSourceOptions
                        .firstWhere((o) => o.label == value, orElse: () => incomeSourceOptions.last)
                        .value;
                  }
                }),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _notes,
                maxLength: 500,
                decoration: const InputDecoration(labelText: 'Notes (optional)'),
              ),
              const SizedBox(height: 8),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.event),
                title: const Text('Date received'),
                subtitle: Text(formatDate(_date)),
                trailing: TextButton(onPressed: _pickDate, child: const Text('Change')),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: (_busy || currency == null) ? null : () => _save(currency),
                child: _busy
                    ? const SizedBox(
                        height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Save income'),
              ),
              if (settings.hasError) ...[
                const SizedBox(height: 12),
                const Text('Couldn’t load your base currency. Pull back and retry.',
                    textAlign: TextAlign.center),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

String? _validateAmount(String? raw) {
  final v = (raw ?? '').trim();
  if (v.isEmpty) return 'Enter an amount';
  final n = double.tryParse(v);
  if (n == null) return 'Enter a valid number';
  if (n <= 0) return 'Amount must be greater than 0';
  final dot = v.indexOf('.');
  if (dot != -1 && v.length - dot - 1 > 4) return 'At most 4 decimal places';
  return null;
}
