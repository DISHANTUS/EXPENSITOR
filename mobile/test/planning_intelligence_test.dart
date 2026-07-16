import 'package:expensitor_mobile/features/budget_setup/planning_intelligence.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('subscriptionAdvice', () {
    test('a shared plan is never second-guessed', () {
      expect(
        subscriptionAdvice(name: 'Netflix', monthly: 649, shared: true, currency: 'INR'),
        isNull,
      );
    });

    test('a cheap solo plan needs no advice', () {
      expect(
        subscriptionAdvice(name: 'Spotify', monthly: 119, shared: false, currency: 'INR'),
        isNull,
      );
    });

    test('a pricey solo plan gets a gentle, non-pushy suggestion', () {
      final advice = subscriptionAdvice(name: 'Netflix', monthly: 649, shared: false, currency: 'INR');
      expect(advice, isNotNull);
      expect(advice!.headline.toLowerCase(), contains('netflix'));
      // It must stay a suggestion, never a mandate.
      expect(advice.detail.toLowerCase(), contains('completely fine'));
      // It should not invent a specific cheaper price (that data we don't have).
      expect(advice.detail, isNot(contains('₹200')));
    });

    test('the review threshold scales by currency magnitude', () {
      // Same "premium" size in USD is a much smaller number than in INR.
      expect(subscriptionAdvice(name: 'x', monthly: 15, shared: false, currency: 'USD'), isNotNull);
      expect(subscriptionAdvice(name: 'x', monthly: 8, shared: false, currency: 'USD'), isNull);
      expect(subscriptionAdvice(name: 'x', monthly: 900, shared: false, currency: 'INR'), isNotNull);
    });

    test('an unknown currency falls back to a sane default threshold', () {
      expect(subscriptionAdvice(name: 'x', monthly: 1000, shared: false, currency: 'XYZ'), isNotNull);
      expect(subscriptionAdvice(name: 'x', monthly: 50, shared: false, currency: 'XYZ'), isNull);
    });
  });
}
