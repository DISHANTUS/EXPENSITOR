import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/format/dates.dart';
import '../../core/settings/settings_repository.dart';
import 'ledger_actions.dart';
import 'ledger_models.dart';
import 'ledger_repository.dart';

class AddEventScreen extends ConsumerStatefulWidget {
  const AddEventScreen({super.key, required this.date});

  final DateTime date;

  @override
  ConsumerState<AddEventScreen> createState() => _AddEventScreenState();
}

class _AddEventScreenState extends ConsumerState<AddEventScreen> {
  final _formKey = GlobalKey<FormState>();
  final _title = TextEditingController();
  final _amount = TextEditingController();
  final _notes = TextEditingController();
  String? _occasion;
  bool _busy = false;

  @override
  void dispose() {
    _title.dispose();
    _amount.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _save(String currency) async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      await ref.read(ledgerRepositoryProvider).createEvent(
            title: _title.text,
            amount: _amount.text.trim(),
            currency: currency,
            date: widget.date,
            occasionType: _occasion,
            notes: _notes.text,
          );
      if (!mounted) return;
      completeLedgerWrite(context, ref, kind: 'event');
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
        title: const Text('Add event'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.go('/date/${ymd(widget.date)}'),
        ),
      ),
      body: AbsorbPointer(
        absorbing: _busy,
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            children: [
              Text('Planned for ${formatDate(widget.date)}',
                  style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 12),
              TextFormField(
                controller: _title,
                autofocus: true,
                maxLength: 255,
                decoration: const InputDecoration(labelText: 'What is it? (e.g. Outing with friends)'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Give the event a name' : null,
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _amount,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
                decoration: InputDecoration(
                  labelText: 'Planned amount',
                  prefixText: currency == null ? null : '$currency  ',
                ),
                validator: _validateAmount,
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String?>(
                initialValue: _occasion,
                decoration: const InputDecoration(labelText: 'Occasion (optional)'),
                items: [
                  const DropdownMenuItem<String?>(value: null, child: Text('None')),
                  ...occasionOptions.map((o) => DropdownMenuItem<String?>(value: o.value, child: Text(o.label))),
                ],
                onChanged: (v) => setState(() => _occasion = v),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _notes,
                maxLength: 2000,
                decoration: const InputDecoration(labelText: 'Notes / reason (optional)'),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: (_busy || currency == null) ? null : () => _save(currency),
                child: _busy
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Save event'),
              ),
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
