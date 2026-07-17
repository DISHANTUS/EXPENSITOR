import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/settings/settings_repository.dart';
import '../ledger/ledger_actions.dart';
import '../ledger/ledger_repository.dart';
import 'transaction_capture.dart';

/// "You spent ₹50 to swiggy — what for?" — the one-tap confirm for a captured
/// transaction. This is the payoff of the whole capture idea: the amount and
/// payee are already filled from the bank SMS, and the reasons are the user's
/// own learned chips, so recording a spend is a single tap.
///
/// Nothing is written until the user confirms. They can pick a learned reason,
/// type their own, or dismiss entirely — a misread SMS costs one swipe, never a
/// phantom expense.
Future<bool> showTransactionConfirmSheet(BuildContext context, TxnCandidate candidate) async {
  final recorded = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    builder: (_) => Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: _ConfirmBody(candidate: candidate),
    ),
  );
  return recorded ?? false;
}

class _ConfirmBody extends ConsumerStatefulWidget {
  const _ConfirmBody({required this.candidate});
  final TxnCandidate candidate;
  @override
  ConsumerState<_ConfirmBody> createState() => _ConfirmBodyState();
}

class _ConfirmBodyState extends ConsumerState<_ConfirmBody> {
  final _reason = TextEditingController();
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    // Seed with the merchant guess only — never a reason the user didn't give.
    final seed = widget.candidate.suggestedReason;
    if (seed != null) _reason.text = seed;
  }

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _record() async {
    final c = widget.candidate;
    final currency = ref.read(userSettingsProvider).valueOrNull?.baseCurrency ?? 'INR';
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      final repo = ref.read(ledgerRepositoryProvider);
      if (c.isExpense) {
        await repo.createExpense(
          amount: c.amount, currency: currency, date: DateTime.now(),
          description: _reason.text.trim(),
        );
      } else {
        await repo.createIncome(
          // A one-off transfer (e.g. money from family), not a recurring salary.
          sourceType: 'other', amount: c.amount, currency: currency, date: DateTime.now(),
          description: _reason.text.trim().isEmpty ? (c.merchant ?? 'Received') : _reason.text.trim(),
        );
      }
      refreshAfterWrite(ref);
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      // The typed reason stays put on failure — never eat what they wrote.
      messenger.showSnackBar(SnackBar(content: Text(e is AppError ? e.message : "Couldn't record that")));
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.candidate;
    final currency = ref.watch(userSettingsProvider).valueOrNull?.baseCurrency ?? 'INR';
    final verb = c.isExpense ? 'spent' : 'received';
    final tail = c.merchant == null ? '' : (c.isExpense ? ' to ${c.merchant}' : ' from ${c.merchant}');

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(c.isExpense ? Icons.south_east : Icons.north_east,
                  color: c.isExpense ? const Color(0xFFE57373) : const Color(0xFF66BB6A)),
              const SizedBox(width: 8),
              Expanded(
                child: Text('You $verb $currency ${c.amount}$tail',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
              ),
            ]),
            if (c.isUpi)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('Seen in a UPI message', style: Theme.of(context).textTheme.bodySmall),
              ),
            const SizedBox(height: 16),
            if (c.isExpense) ...[
              Text('What was this for?', style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 6),
              if (c.reasons.isNotEmpty)
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    for (final r in c.reasons)
                      ActionChip(
                        label: Text(r),
                        onPressed: () => setState(() {
                          _reason.text = r;
                          _reason.selection = TextSelection.collapsed(offset: r.length);
                        }),
                      ),
                  ],
                ),
              const SizedBox(height: 8),
              TextField(
                controller: _reason,
                autofocus: c.reasons.isEmpty,
                decoration: const InputDecoration(
                  hintText: 'Reason (or tap one above)',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ],
            const SizedBox(height: 16),
            Row(children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: _busy ? null : () => Navigator.of(context).pop(false),
                  child: const Text('Not now'),
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
    );
  }
}
