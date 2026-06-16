const _months = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/// "16 Jun 2026". Falls back to "—" for null.
String formatDate(DateTime? d) {
  if (d == null) return '—';
  return '${d.day} ${_months[d.month - 1]} ${d.year}';
}
