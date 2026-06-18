import 'package:flutter_test/flutter_test.dart';
import 'package:expensitor_mobile/core/facts/facts_repository.dart';

void main() {
  group('FactsRepository.parseFacts (offline path)', () {
    const raw = '''
1000 FACTS ABOUT FOOD
======================

--- FRUIT ---

1. Honey never spoils and has been found edible in ancient tombs.
2. Bananas are berries, but strawberries are not.

--- SPICES ---

3. Saffron is among the most expensive spices by weight.

==============
END OF 1000 FOOD FACTS
==============
''';

    test('keeps only the fact text, stripping the leading number', () {
      expect(FactsRepository.parseFacts(raw), [
        'Honey never spoils and has been found edible in ancient tombs.',
        'Bananas are berries, but strawberries are not.',
        'Saffron is among the most expensive spices by weight.',
      ]);
    });

    test('never leaks a banner, divider, footer or serial number', () {
      final facts = FactsRepository.parseFacts(raw);
      final blob = facts.join('\n');
      expect(blob.contains('1000 FACTS'), isFalse);
      expect(blob.contains('END OF'), isFalse);
      expect(blob.contains('---') || blob.contains('==='), isFalse);
      for (final f in facts) {
        expect(RegExp(r'^\s*\d+\.').hasMatch(f), isFalse);
      }
    });

    test('ignores stray non-fact lines', () {
      expect(FactsRepository.parseFacts('--- ASIA ---\n\nJust a sentence.\n1990 was a year.'), isEmpty);
    });
  });
}
