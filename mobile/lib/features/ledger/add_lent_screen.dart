import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/format/dates.dart';
import '../../core/settings/settings_repository.dart';
import '../budget_setup/budget_repository.dart';
import 'ledger_actions.dart';

class AddLentScreen extends ConsumerStatefulWidget {
  const AddLentScreen({super.key, required this.date});
  final DateTime date;

  @override
  ConsumerState<AddLentScreen> createState() => _AddLentScreenState();
}

class _AddLentScreenState extends ConsumerState<AddLentScreen> {
  final _formKey = GlobalKey<FormState>();
  final _person = TextEditingController();
  final _amount = TextEditingController();
  final _reason = TextEditingController();
  late DateTime _returnBy = widget.date.add(const Duration(days: 7));
  bool _busy = false;

  @override
  void dispose() {
    _person.dispose();
    _amount.dispose();
    _reason.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _returnBy,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );
    if (picked != null) setState(() => _returnBy = picked);
  }

  Future<void> _save(String currency) async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      // Preserve the user's words AND store the AI's label + tags (store both).
      Map<String, dynamic>? meta;
      final reasonText = _reason.text.trim();
      if (reasonText.isNotEmpty) {
        try {
          meta = (await ref.read(settingsRepositoryProvider).interpretReason(reasonText)).toMetadata();
        } on AppError {
          meta = {'why_original': reasonText};
        }
      }
      await ref.read(budgetRepositoryProvider).createLentMoney(
            personName: _person.text.trim(),
            amount: _amount.text.trim(),
            currency: currency,
            expectedReturn: _returnBy,
            reason: reasonText,
            aiMetadata: meta,
          );
      if (!mounted) return;
      completeLedgerWrite(context, ref, kind: 'lent');
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
        title: const Text('Lent money'),
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
                decoration: const InputDecoration(labelText: 'Who did you lend to?'),
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
              const SizedBox(height: 8),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.event),
                title: const Text('Expected back by'),
                subtitle: Text(formatDate(_returnBy)),
                trailing: TextButton(onPressed: _pickDate, child: const Text('Change')),
              ),
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
