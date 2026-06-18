import 'package:expensitor_mobile/features/budget_setup/budget_setup_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('income source choice maps to backend source_type', () {
    expect(mapIncomeSourceType('Salary'), 'salary');
    expect(mapIncomeSourceType('Freelancing'), 'freelance');
    expect(mapIncomeSourceType('Business'), 'business');
    expect(mapIncomeSourceType('Family support'), 'other');
    expect(mapIncomeSourceType('Other'), 'other');
  });

  test('commitment choice maps to backend rule_type', () {
    expect(mapCommitmentRuleType('EMI'), 'emi');
    expect(mapCommitmentRuleType('Subscription'), 'subscription');
    expect(mapCommitmentRuleType('Insurance'), 'insurance');
    expect(mapCommitmentRuleType('Loan'), 'loan');
    expect(mapCommitmentRuleType('Rent'), 'bill');
    expect(mapCommitmentRuleType('Other'), 'bill');
  });

  test('BudgetDraft round-trips through encode/decode (resumability)', () {
    final d = BudgetDraft(
      step: 4,
      incomeSource: 'Family support',
      familyWho: ['Father', 'Mother'],
      incomeAmount: '30000',
      incomeWhy: 'Family help',
      commitments: [Commitment(type: 'Subscription', label: 'Netflix', amount: '200', day: 15, why: 'anime')],
      goals: [GoalDraft(name: 'Japan fund', amount: '5000', why: 'Travel')],
    );
    final back = BudgetDraft.decode(d.encode());
    expect(back.step, 4);
    expect(back.incomeSource, 'Family support');
    expect(back.familyWho, ['Father', 'Mother']);
    expect(back.incomeAmount, '30000');
    expect(back.commitments.single.label, 'Netflix');
    expect(back.commitments.single.day, 15);
    expect(back.goals.single.name, 'Japan fund');
    expect(back.goals.single.why, 'Travel');
  });
}
