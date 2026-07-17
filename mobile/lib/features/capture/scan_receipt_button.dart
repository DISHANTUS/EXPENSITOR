import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import 'receipt_confirm_sheet.dart';
import 'receipt_scan_service.dart';
import 'transaction_capture.dart';

/// "Scan" — photograph a receipt and let the app fill the expense.
///
/// The whole flow in one place: camera → on-device OCR → the (already-live)
/// receipt parser → the confirm sheet. Every failure mode ends quietly, because
/// the manual add buttons sit right next to this one: a cancelled camera, an
/// unreadable photo or a non-receipt image just does nothing rather than
/// erroring at the user.
class ScanReceiptButton extends ConsumerStatefulWidget {
  const ScanReceiptButton({super.key});

  @override
  ConsumerState<ScanReceiptButton> createState() => _ScanReceiptButtonState();
}

class _ScanReceiptButtonState extends ConsumerState<ScanReceiptButton> {
  bool _busy = false;

  Future<void> _scan() async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      final text = await ref.read(receiptScanServiceProvider).scanText();
      if (text == null) {
        // Cancelled or nothing readable — say nothing.
        if (mounted) setState(() => _busy = false);
        return;
      }
      final candidate = await ref.read(transactionCaptureRepositoryProvider).parseReceipt(text);
      if (!mounted) return;
      setState(() => _busy = false);
      if (candidate == null) {
        messenger.showSnackBar(const SnackBar(
          content: Text("Couldn't read a receipt in that photo — try again, or add it by hand."),
        ));
        return;
      }
      await showReceiptConfirmSheet(context, candidate);
    } catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      messenger.showSnackBar(SnackBar(content: Text(e is AppError ? e.message : "Couldn't scan that")));
    }
  }

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: _busy ? null : _scan,
      icon: _busy
          ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2))
          : const Icon(Icons.document_scanner_outlined),
      label: const Text('Scan'),
    );
  }
}
