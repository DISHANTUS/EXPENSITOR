import '../../core/format/money.dart';

/// A gentle, non-pushy suggestion about a subscription — surfaced after the
/// user says who'll use it. The knowledge is deliberately heuristic, not a
/// fabricated per-service price list: premium/4K/multi-screen tiers exist to be
/// shared across people and devices, so a single user on a high monthly is
/// usually paying for capacity they won't use. We say that honestly and let
/// the user keep their choice either way.
class SubscriptionAdvice {
  const SubscriptionAdvice({required this.headline, required this.detail});
  final String headline;
  final String detail;
}

// Below this monthly cost there's little worth second-guessing — a suggestion
// would just be noise. Tuned per rough currency magnitude.
const _soloReviewThreshold = <String, double>{
  'INR': 400,
  'USD': 12,
  'EUR': 12,
  'GBP': 10,
  'JPY': 1500,
  'CZK': 250,
};

SubscriptionAdvice? subscriptionAdvice({
  required String name,
  required double monthly,
  required bool shared,
  required String currency,
}) {
  // Shared plans are exactly what the higher tiers are for — nothing to flag.
  if (shared) return null;

  final threshold = _soloReviewThreshold[currency.toUpperCase()] ?? 400;
  if (monthly < threshold) return null;

  final label = name.isEmpty ? 'this' : name;
  final cost = formatMoneyValue(monthly, currency);
  return SubscriptionAdvice(
    headline: 'For just you, $label\'s top tier may be more than you need.',
    detail:
        'The pricier plans are built for sharing — multiple screens at once, 4K, '
        'a whole household. On your own you likely won\'t use most of that, and a '
        'cheaper tier usually still looks great on one phone or laptop. Worth a '
        'quick look before locking in $cost a month — but if you want the top '
        'plan, that\'s completely fine.',
  );
}
