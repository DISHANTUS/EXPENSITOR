import 'package:flutter/material.dart';

import '../../../core/format/money.dart';
import '../predicted_expense_repository.dart';

/// "Is the ₹200 for travel over?" — a learned habit offered for one-tap
/// confirmation on the compact Home, so the usual daily spend doesn't need
/// typing. **Yes** logs it, **No** dismisses it for today, and the amount is
/// editable inline for when the usual number changed.
///
/// Nothing is written until the user taps — a wrong prediction costs one
/// ignored card, never a bad expense row.
class SpendConfirmCard extends StatefulWidget {
  const SpendConfirmCard({
    super.key,
    required this.prediction,
    required this.currency,
    required this.onConfirm,
    required this.onDismiss,
  });

  final PredictedExpense prediction;
  final String currency;

  /// Returns null on success, or a message to show inline. [amount] is the
  /// (possibly corrected) value the user actually confirmed.
  final Future<String?> Function(double amount) onConfirm;
  final VoidCallback onDismiss;

  @override
  State<SpendConfirmCard> createState() => _SpendConfirmCardState();
}

class _SpendConfirmCardState extends State<SpendConfirmCard> {
  late final TextEditingController _amount =
      TextEditingController(text: _trim(widget.prediction.amount));
  bool _editing = false;
  bool _sending = false;
  String? _notice;

  static String _trim(double v) => v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(2);

  @override
  void dispose() {
    _amount.dispose();
    super.dispose();
  }

  Future<void> _confirm() async {
    if (_sending) return;
    final value = double.tryParse(_amount.text.trim());
    if (value == null || value <= 0) {
      setState(() => _notice = 'Enter an amount above zero.');
      return;
    }
    setState(() {
      _sending = true;
      _notice = null;
    });
    final notice = await widget.onConfirm(value);
    if (!mounted) return;
    setState(() {
      _sending = false;
      _notice = notice;   // null == logged; the card disappears on refetch
    });
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    final p = widget.prediction;
    final shown = double.tryParse(_amount.text.trim()) ?? p.amount;

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      color: cs.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.replay_outlined, size: 18, color: cs.primary),
              const SizedBox(width: 6),
              const Text('Usual for today', style: TextStyle(fontWeight: FontWeight.w600)),
            ]),
            const SizedBox(height: 8),
            if (_editing)
              Row(children: [
                Expanded(
                  child: TextField(
                    controller: _amount,
                    autofocus: true,
                    enabled: !_sending,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: InputDecoration(
                      prefixText: '${currencySymbol(widget.currency)} ',
                      isDense: true,
                      border: const OutlineInputBorder(),
                      labelText: '${p.label} today',
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                TextButton(
                  onPressed: _sending ? null : () => setState(() => _editing = false),
                  child: const Text('Done'),
                ),
              ])
            else
              Text('Is the ${formatMoneyValue(shown, widget.currency)} for ${p.label} over?'),
            if (_notice != null) ...[
              const SizedBox(height: 6),
              Text(_notice!, style: tt.bodySmall?.copyWith(color: cs.primary)),
            ],
            const SizedBox(height: 10),
            // Wrap, not Row+Spacer: a bare Row with a Spacer demands a bounded
            // width, which this card (inside a Column inside the Home list) is
            // not always given — that unbounded-width assert silently collapsed
            // the whole card to zero size. Wrap sizes to content and reflows.
            Wrap(
              spacing: 8,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                FilledButton(
                  onPressed: _sending ? null : _confirm,
                  child: _sending
                      ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('Yes'),
                ),
                OutlinedButton(
                  onPressed: _sending ? null : widget.onDismiss,
                  child: const Text('No'),
                ),
                if (!_editing)
                  TextButton.icon(
                    onPressed: _sending ? null : () => setState(() => _editing = true),
                    icon: const Icon(Icons.edit_outlined, size: 16),
                    label: const Text('Amount changed'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
