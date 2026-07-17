import 'package:expensitor_mobile/features/capture/transaction_capture.dart';
import 'package:flutter_test/flutter_test.dart';

/// The parse-and-confirm pipeline. The confirm SHEET is exercised on a device
/// (it opens a modal + records via the ledger); here we pin the model mapping,
/// which is the part that silently breaks when the API shape drifts.
void main() {
  group('TxnCandidate.fromJson', () {
    test('maps a debit into an expense with its learned reasons', () {
      final c = TxnCandidate.fromJson({
        'kind': 'expense',
        'direction': 'debit',
        'amount': '50.00',
        'merchant': 'swiggy@ybl',
        'is_upi': true,
        'suggested_reason': 'swiggy@ybl',
        'reasons': ['chai', 'lunch'],
        'raw': 'Rs 50 debited to swiggy@ybl',
      });
      expect(c.isExpense, isTrue);
      expect(c.amount, '50.00');
      expect(c.merchant, 'swiggy@ybl');
      expect(c.isUpi, isTrue);
      expect(c.reasons, ['chai', 'lunch']);
    });

    test('maps a credit into income', () {
      final c = TxnCandidate.fromJson({
        'kind': 'income', 'direction': 'credit', 'amount': '5000',
        'merchant': 'dad@upi', 'is_upi': true, 'reasons': const [], 'raw': 'x',
      });
      expect(c.isExpense, isFalse);
      expect(c.kind, 'income');
    });

    test('tolerates missing optional fields', () {
      final c = TxnCandidate.fromJson({'kind': 'expense', 'amount': '10', 'raw': 'x'});
      expect(c.merchant, isNull);
      expect(c.isUpi, isFalse);
      expect(c.reasons, isEmpty);
      expect(c.suggestedReason, isNull);
    });
  });
}
