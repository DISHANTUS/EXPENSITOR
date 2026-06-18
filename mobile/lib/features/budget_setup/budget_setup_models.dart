// Pure data + mappings for the Budget Setup interview (unit-tested; no UI).

import 'dart:convert';

// Note: lists omit "Other" — the OtherableChips widget adds an "Other → type"
// affordance itself, so a custom value is captured (never stored as "Other").

/// Step 1 — income source chips → backend income source_type.
const incomeSourceOptions = ['Salary', 'Family support', 'Freelancing', 'Business'];

String mapIncomeSourceType(String choice) {
  switch (choice) {
    case 'Salary':
      return 'salary';
    case 'Freelancing':
      return 'freelance';
    case 'Business':
      return 'business';
    case 'Family support': // income_sources has no 'family'; keep nuance in reason/Person
      return 'other';
    default:
      return 'other';
  }
}

const familyWhoOptions = ['Father', 'Mother', 'Both', 'Relative', 'Other'];

/// Step 3 — recurring commitment type chips → backend recurring_rule_type.
const commitmentTypeOptions = ['Rent', 'EMI', 'Subscription', 'Insurance', 'Loan', 'Other'];

String mapCommitmentRuleType(String choice) {
  switch (choice) {
    case 'EMI':
      return 'emi';
    case 'Subscription':
      return 'subscription';
    case 'Insurance':
      return 'insurance';
    case 'Loan':
      return 'loan';
    case 'Rent':
    case 'Other':
    default:
      return 'bill';
  }
}

/// "Why" suggestion chips (options-first; OtherableChips adds custom text).
const incomeWhyOptions = ['Job', 'Side work', 'Family help', 'Business'];
const goalWhyOptions = ['Education', 'Travel', 'Family', 'Emergency fund', 'Investment'];

class Commitment {
  Commitment({required this.type, required this.label, required this.amount, required this.day, this.why});
  String type;
  String label;
  String amount;
  int day;
  String? why;

  Map<String, dynamic> toJson() => {'type': type, 'label': label, 'amount': amount, 'day': day, 'why': why};
  factory Commitment.fromJson(Map<String, dynamic> j) => Commitment(
        type: j['type'].toString(),
        label: j['label'].toString(),
        amount: j['amount'].toString(),
        day: (j['day'] as num?)?.toInt() ?? 1,
        why: j['why'] as String?,
      );
}

class GoalDraft {
  GoalDraft({required this.name, required this.amount, this.why});
  String name;
  String amount;
  String? why;

  Map<String, dynamic> toJson() => {'name': name, 'amount': amount, 'why': why};
  factory GoalDraft.fromJson(Map<String, dynamic> j) =>
      GoalDraft(name: j['name'].toString(), amount: j['amount'].toString(), why: j['why'] as String?);
}

/// The whole in-progress interview — persisted so it's resumable.
class BudgetDraft {
  BudgetDraft({
    this.step = 0,
    this.incomeSource,
    List<String>? familyWho,
    this.incomeAmount = '',
    this.incomeWhy,
    List<Commitment>? commitments,
    List<GoalDraft>? goals,
  })  : familyWho = familyWho ?? [],
        commitments = commitments ?? [],
        goals = goals ?? [];

  int step;
  String? incomeSource;
  List<String> familyWho;
  String incomeAmount;
  String? incomeWhy;
  List<Commitment> commitments;
  List<GoalDraft> goals;

  Map<String, dynamic> toJson() => {
        'step': step,
        'incomeSource': incomeSource,
        'familyWho': familyWho,
        'incomeAmount': incomeAmount,
        'incomeWhy': incomeWhy,
        'commitments': commitments.map((c) => c.toJson()).toList(),
        'goals': goals.map((g) => g.toJson()).toList(),
      };

  factory BudgetDraft.fromJson(Map<String, dynamic> j) => BudgetDraft(
        step: (j['step'] as num?)?.toInt() ?? 0,
        incomeSource: j['incomeSource'] as String?,
        familyWho: ((j['familyWho'] as List?) ?? const []).map((e) => e.toString()).toList(),
        incomeAmount: (j['incomeAmount'] ?? '').toString(),
        incomeWhy: j['incomeWhy'] as String?,
        commitments: ((j['commitments'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => Commitment.fromJson(e.cast<String, dynamic>()))
            .toList(),
        goals: ((j['goals'] as List?) ?? const [])
            .whereType<Map>()
            .map((e) => GoalDraft.fromJson(e.cast<String, dynamic>()))
            .toList(),
      );

  String encode() => jsonEncode(toJson());
  static BudgetDraft decode(String s) => BudgetDraft.fromJson(jsonDecode(s) as Map<String, dynamic>);
}
