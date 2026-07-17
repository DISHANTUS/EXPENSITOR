import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/settings/settings_repository.dart';
import '../ledger/ledger_actions.dart';
import '../ledger/ledger_repository.dart';
import 'transaction_capture.dart';

/// Review a scanned receipt before it's recorded. Shows the total (the expense),
/// each line with "you usually pay X" when known, and the learned reason chips.
///
/// Nothing is written until Record: the total becomes one expense, and the line
/// items become this user's own price history. A bad scan costs one dismiss,
/// never a wrong expense — same discipline as the SMS confirm.
Future<bool> showReceiptConfirmSheet(BuildContext context, ReceiptCandidate candidate) async {
  final recorded = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    builder: (_) => Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: _ReceiptBody(candidate: candidate),
    ),
  );
  return recorded ?? false;
}

class _ReceiptBody extends ConsumerStatefulWidget {
  const _ReceiptBody({required this.candidate});
  final ReceiptCandidate candidate;
  @override
  ConsumerState<_ReceiptBody> createState() => _ReceiptBodyState();
}

class _ReceiptBodyState extends ConsumerState<_ReceiptBody> {
  final _reason = TextEditingController();
  final _total = TextEditingController();
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _total.text = widget.candidate.total ?? '';
    if (widget.candidate.merchant != null) _reason.text = widget.candidate.merchant!;
  }

  @override
  void dispose() {
    _reason.dispose();
    _total.dispose();
    super.dispose();
  }

  Future<void> _record() async {
    final total = _total.text.trim();
    if (total.isEmpty || (double.tryParse(total) ?? 0) <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Enter the total to record.')));
      return;
    }
    final c = widget.candidate;
    final currency = ref.read(userSettingsProvider).valueOrNull?.baseCurrency ?? 'INR';
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      final observedOn = c.date == null ? DateTime.now() : (DateTime.tryParse(c.date!) ?? DateTime.now());
      // The expense (the total) — the thing that hits the ledger.
      await ref.read(ledgerRepositoryProvider).createExpense(
            amount: total, currency: currency, date: observedOn,
            description: _reason.text.trim(),
          );
      // The line items — this user's own price history. Best-effort: a failure
      // here must not lose the expense that already recorded.
      if (c.items.isNotEmpty) {
        try {
          await ref.read(transactionCaptureRepositoryProvider).recordItems(
                items: [for (final i in c.items) i.toRecordJson()],
                currency: currency, observedOn: observedOn, merchant: c.merchant,
              );
        } catch (_) {/* prices are a bonus, never worth failing the record */}
      }
      refreshAfterWrite(ref);
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      messenger.showSnackBar(SnackBar(content: Text(e is AppError ? e.message : "Couldn't record that")));
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.candidate;
    final currency = ref.watch(userSettingsProvider).valueOrNull?.baseCurrency ?? 'INR';
    final tt = Theme.of(context).textTheme;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                const Icon(Icons.receipt_long_outlined),
                const SizedBox(width: 8),
                Expanded(child: Text(c.merchant ?? 'Receipt',
                    style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w700))),
              ]),
              const SizedBox(height: 12),
              TextField(
                controller: _total,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: InputDecoration(labelText: 'Total', prefixText: '$currency  ', border: const OutlineInputBorder()),
              ),
              if (c.items.isNotEmpty) ...[
                const SizedBox(height: 14),
                Text('Items', style: tt.bodySmall),
                const SizedBox(height: 4),
                for (final it in c.items)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Row(children: [
                      Expanded(child: Text(it.name, style: tt.bodyMedium)),
                      if (it.typicalPrice != null && it.typicalPrice != it.price)
                        Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: Text('usually $currency ${it.typicalPrice}',
                              style: tt.bodySmall?.copyWith(fontStyle: FontStyle.italic)),
                        ),
                      Text('$currency ${it.price}', style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
                    ]),
                  ),
              ],
              const SizedBox(height: 14),
              Text('What was this for?', style: tt.bodySmall),
              const SizedBox(height: 6),
              if (c.reasons.isNotEmpty)
                Wrap(spacing: 8, runSpacing: 4, children: [
                  for (final r in c.reasons)
                    ActionChip(
                      label: Text(r),
                      onPressed: () => setState(() {
                        _reason.text = r;
                        _reason.selection = TextSelection.collapsed(offset: r.length);
                      }),
                    ),
                ]),
              const SizedBox(height: 8),
              TextField(
                controller: _reason,
                decoration: const InputDecoration(hintText: 'Reason', border: OutlineInputBorder(), isDense: true),
              ),
              const SizedBox(height: 16),
              Row(children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _busy ? null : () => Navigator.of(context).pop(false),
                    child: const Text('Discard'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed: _busy ? null : _record,
                    child: _busy
                        ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Text('Record'),
                  ),
                ),
              ]),
            ],
          ),
        ),
      ),
    );
  }
}
