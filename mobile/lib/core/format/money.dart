/// Formats a base-currency string (e.g. "420.0000") the way the backend phrases
/// money: "₹420", "₹15,000". Mirrors the server's symbol set; falls back to the
/// currency code for unknown currencies.
const _symbols = {'INR': '₹', 'USD': '\$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'CZK': 'Kč'};

String currencySymbol(String currency) => _symbols[currency.toUpperCase()] ?? '${currency.toUpperCase()} ';

String formatMoneyValue(double value, String currency) {
  final rounded = value.round();
  final digits = rounded.abs().toString();
  final grouped = StringBuffer();
  for (var i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 == 0) grouped.write(',');
    grouped.write(digits[i]);
  }
  final body = '${rounded < 0 ? '-' : ''}$grouped';
  final sym = _symbols[currency.toUpperCase()];
  return sym != null ? '$sym$body' : '${currency.toUpperCase()} $body';
}

String formatMoney(String? raw, String currency) {
  if (raw == null || raw.isEmpty) return '—';
  final value = double.tryParse(raw);
  if (value == null) return raw;
  return formatMoneyValue(value, currency);
}
