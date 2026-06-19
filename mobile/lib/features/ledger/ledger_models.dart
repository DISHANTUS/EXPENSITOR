// Ledger DTOs + pure helpers for expense/income creation and the merged
// transaction history. Pure functions (bodies, merge, labels) are unit-tested
// without any network.

import '../../core/format/dates.dart';

String? _s(dynamic v) => v?.toString();

/// A pickable expense category (system or user-owned) from GET /categories.
class CategoryOption {
  const CategoryOption({required this.id, required this.name, this.isEssential = false});

  factory CategoryOption.fromJson(Map<String, dynamic> j) => CategoryOption(
        id: j['id'].toString(),
        name: _s(j['name']) ?? '',
        isEssential: j['is_essential'] == true,
      );

  final String id;
  final String name;
  final bool isEssential;
}

/// Income source types accepted by POST /incomes (backend IncomeSourceType enum).
const incomeSourceOptions = <({String value, String label})>[
  (value: 'salary', label: 'Salary'),
  (value: 'freelance', label: 'Freelance'),
  (value: 'bonus', label: 'Bonus'),
  (value: 'business', label: 'Business'),
  (value: 'gift', label: 'Gift'),
  (value: 'refund', label: 'Refund'),
  (value: 'other', label: 'Other'),
];

String incomeSourceLabel(String value) => incomeSourceOptions
    .firstWhere((o) => o.value == value, orElse: () => (value: value, label: value))
    .label;

/// Build the POST /expenses body. Omits optional fields when empty so the
/// backend's `extra="forbid"` schema never rejects a null/blank.
Map<String, dynamic> expenseBody({
  required String amount,
  required String currency,
  required DateTime date,
  String? categoryId,
  String? description,
}) =>
    {
      'original_amount': amount,
      'original_currency': currency.toUpperCase(),
      'expense_date': ymd(date),
      if (categoryId != null && categoryId.isNotEmpty) 'category_id': categoryId,
      if (description != null && description.trim().isNotEmpty) 'description': description.trim(),
    };

/// Planner-event occasion types accepted by POST /planned-expenses. Advary
/// normally assigns one from the title; this list is only the manual override.
const occasionOptions = <({String value, String label})>[
  (value: 'outing', label: '❤️ Outing'),
  (value: 'date', label: '❤️ Date'),
  (value: 'birthday', label: '🎂 Birthday'),
  (value: 'anniversary', label: '💞 Anniversary'),
  (value: 'travel', label: '✈️ Travel'),
  (value: 'vacation', label: '✈️ Vacation'),
  (value: 'celebration', label: '🎉 Celebration'),
  (value: 'festival', label: '🪔 Festival'),
  (value: 'graduation', label: '🎓 Graduation'),
  (value: 'study', label: '📚 Study / exam'),
  (value: 'medical', label: '🏥 Medical'),
  (value: 'gaming', label: '🎮 Gaming'),
  (value: 'food', label: '🍔 Food'),
  (value: 'entertainment', label: '🎬 Entertainment'),
  (value: 'shopping', label: '🛒 Shopping'),
];

/// Build the POST /planned-expenses body (a calendar event). Amount is optional —
/// an event doubles as a note/reminder (birthday, exam, "call parents"), so it's
/// omitted when blank and the backend stores 0.
Map<String, dynamic> eventBody({
  required String title,
  required String currency,
  required DateTime date,
  String? amount,
  String? occasionType,
  String? notes,
}) =>
    {
      'title': title.trim(),
      'planned_date': ymd(date),
      if (amount != null && amount.trim().isNotEmpty) 'original_amount': amount.trim(),
      'original_currency': currency.toUpperCase(),
      if (occasionType != null && occasionType.isNotEmpty) 'occasion_type': occasionType,
      if (notes != null && notes.trim().isNotEmpty) 'notes': notes.trim(),
    };

/// Build the POST /incomes body.
Map<String, dynamic> incomeBody({
  required String sourceType,
  required String amount,
  required String currency,
  required DateTime date,
  String? description,
}) =>
    {
      'source_type': sourceType,
      'original_amount': amount,
      'original_currency': currency.toUpperCase(),
      'received_date': ymd(date),
      if (description != null && description.trim().isNotEmpty) 'description': description.trim(),
    };

/// A unified history row (an expense or an income), already in base currency.
class Txn {
  const Txn({
    required this.isCredit,
    required this.amount,
    required this.currency,
    required this.date,
    required this.title,
    required this.sortAt,
    this.categoryId,
    this.sourceLabel,
  });

  factory Txn.fromExpense(Map<String, dynamic> j) {
    final desc = _s(j['description']);
    return Txn(
      isCredit: false,
      amount: _s(j['converted_amount']) ?? _s(j['original_amount']) ?? '0',
      currency: _s(j['base_currency']) ?? _s(j['original_currency']) ?? 'INR',
      date: _parseDate(j['expense_date']),
      title: (desc != null && desc.isNotEmpty) ? desc : 'Expense',
      categoryId: _s(j['category_id']),
      sortAt: _parseDate(j['created_at']) ?? _parseDate(j['expense_date']) ?? DateTime(1970),
    );
  }

  factory Txn.fromIncome(Map<String, dynamic> j) {
    final desc = _s(j['description']);
    final src = _s(j['source_type']) ?? 'other';
    return Txn(
      isCredit: true,
      amount: _s(j['converted_amount']) ?? _s(j['original_amount']) ?? '0',
      currency: _s(j['base_currency']) ?? _s(j['original_currency']) ?? 'INR',
      date: _parseDate(j['received_date']),
      title: (desc != null && desc.isNotEmpty) ? desc : incomeSourceLabel(src),
      sourceLabel: incomeSourceLabel(src),
      sortAt: _parseDate(j['created_at']) ?? _parseDate(j['received_date']) ?? DateTime(1970),
    );
  }

  final bool isCredit;
  final String amount;
  final String currency;
  final DateTime? date;
  final String title;
  final String? categoryId; // expense only
  final String? sourceLabel; // income only
  final DateTime sortAt;
}

DateTime? _parseDate(dynamic v) {
  if (v == null) return null;
  return DateTime.tryParse(v.toString());
}

/// Merge expenses + incomes into one newest-first list. Pure → unit-tested.
List<Txn> mergeTransactions(List<Txn> expenses, List<Txn> incomes) {
  final all = [...expenses, ...incomes]..sort((a, b) => b.sortAt.compareTo(a.sortAt));
  return all;
}
