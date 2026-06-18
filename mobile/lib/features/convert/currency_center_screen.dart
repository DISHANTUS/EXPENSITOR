import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/format/money.dart';
import '../../core/settings/settings_repository.dart';
import '../settings/settings_screen.dart';

class CurrencyCenterScreen extends ConsumerStatefulWidget {
  const CurrencyCenterScreen({super.key});

  @override
  ConsumerState<CurrencyCenterScreen> createState() => _CurrencyCenterScreenState();
}

class _CurrencyCenterScreenState extends ConsumerState<CurrencyCenterScreen> {
  final _amount = TextEditingController(text: '1000');
  String? _from;
  String? _to;
  String? _result;
  bool _busy = false;

  @override
  void dispose() {
    _amount.dispose();
    super.dispose();
  }

  Future<void> _convert() async {
    final from = _from, to = _to;
    final amt = _amount.text.trim();
    if (from == null || to == null || double.tryParse(amt) == null) return;
    setState(() => _busy = true);
    try {
      final out = await ref.read(settingsRepositoryProvider).convert(amt, from, to);
      setState(() {
        _result = '${formatMoney(amt, from)}  =  ${formatMoney(out, to)}';
        _busy = false;
      });
    } on AppError catch (e) {
      setState(() => _busy = false);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(userSettingsProvider);
    final base = settings.valueOrNull?.baseCurrency ?? 'INR';
    final codes = ref.watch(currenciesProvider).valueOrNull ?? const ['INR', 'USD', 'EUR', 'GBP', 'JPY'];
    _from ??= base;
    _to ??= codes.firstWhere((c) => c != base, orElse: () => base);

    return CompanionScaffold(
      title: 'Currency Center',
      commentary: 'Your currency is $base. Convert anything, or change what the whole app uses.',
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.public),
              title: const Text('Preferred currency'),
              trailing: Text(base, style: Theme.of(context).textTheme.titleMedium),
              onTap: () => changePreferredCurrency(context, ref),
            ),
          ),
          const SizedBox(height: 8),
          Text('Convert', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(
            controller: _amount,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))],
            decoration: const InputDecoration(labelText: 'Amount'),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _currencyDropdown('From', _from!, codes, (v) => setState(() => _from = v))),
              const Padding(padding: EdgeInsets.symmetric(horizontal: 8), child: Icon(Icons.arrow_forward)),
              Expanded(child: _currencyDropdown('To', _to!, codes, (v) => setState(() => _to = v))),
            ],
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy ? null : _convert,
            child: _busy
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Convert'),
          ),
          if (_result != null) ...[
            const SizedBox(height: 16),
            Card(child: Padding(padding: const EdgeInsets.all(16), child: Text(_result!, style: Theme.of(context).textTheme.titleMedium))),
          ],
        ],
      ),
    );
  }

  Widget _currencyDropdown(String label, String value, List<String> codes, ValueChanged<String> onChanged) {
    final items = {value, ...codes}.toList();
    return DropdownButtonFormField<String>(
      initialValue: value,
      decoration: InputDecoration(labelText: label),
      items: [for (final c in items) DropdownMenuItem(value: c, child: Text(c))],
      onChanged: (v) => onChanged(v ?? value),
    );
  }
}
