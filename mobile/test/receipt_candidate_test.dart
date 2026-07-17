import 'package:expensitor_mobile/features/capture/transaction_capture.dart';
import 'package:flutter_test/flutter_test.dart';

/// The receipt candidate mapping. The camera + OCR are native (device-tested),
/// but the parse -> model shape is what silently breaks when the API drifts, so
/// that's pinned here.
void main() {
  test('maps a scanned receipt with items and learned usual prices', () {
    final c = ReceiptCandidate.fromJson({
      'merchant': 'FRESH MART',
      'total': '103.00',
      'date': '2026-07-17',
      'items': [
        {'name': 'Milk 1L', 'price': '60.00', 'typical_price': '58.00', 'observations': 3},
        {'name': 'Bread', 'price': '45.00'},
      ],
      'reasons': ['weekly groceries'],
    });
    expect(c.merchant, 'FRESH MART');
    expect(c.total, '103.00');
    expect(c.items.length, 2);

    final milk = c.items.first;
    expect(milk.name, 'Milk 1L');
    expect(milk.price, '60.00');
    expect(milk.typicalPrice, '58.00');   // "you usually pay"
    expect(milk.observations, 3);
    expect(milk.toRecordJson(), {'name': 'Milk 1L', 'price': '60.00'});

    // No history on bread -> no usual price, and that's honest, not a guess.
    expect(c.items[1].typicalPrice, isNull);
    expect(c.reasons, ['weekly groceries']);
  });

  test('tolerates a sparse receipt (total only, no items)', () {
    final c = ReceiptCandidate.fromJson({'total': '500', 'items': const [], 'reasons': const []});
    expect(c.total, '500');
    expect(c.items, isEmpty);
    expect(c.merchant, isNull);
  });
}
