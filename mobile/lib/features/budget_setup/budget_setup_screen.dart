import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/budget/budget_plan_repository.dart';
import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/settings/settings_repository.dart';
import '../../core/widgets/otherable_chips.dart';
import 'budget_repository.dart';

/// Profile-Discovery Wizard (Budget Intelligence System — Phase 5C).
///
/// Profile-first onboarding: get to know the person (country → life stage →
/// living → food → transport → scholarship/part-time → income → daily living →
/// goal → how to optimise) BEFORE doing money math, then land on the Plan screen.
/// Every step explains why it matters, supports Back/Skip, and every "Other"
/// opens a text field. Nothing is ever locked — it's all editable later via Advary.
class BudgetSetupScreen extends ConsumerStatefulWidget {
  const BudgetSetupScreen({super.key});

  @override
  ConsumerState<BudgetSetupScreen> createState() => _BudgetSetupScreenState();
}

// label → stored value maps.
const _countries = {'India': 'IN', 'Japan': 'JP', 'United States': 'US', 'United Kingdom': 'GB'};
const _lifeStages = {
  'School / High School': 'high_school', 'UG Student': 'ug_student', 'PG / Master’s': 'pg_student',
  'Scholarship Student': 'scholarship_student', 'Working Professional': 'working_professional',
  'Self-employed': 'self_employed', 'Business Owner': 'business_owner',
  'Homemaker': 'homemaker', 'Retired': 'retired', 'Between jobs': 'unemployed',
};
const _living = {'Parents': 'with_parents', 'Partner': 'with_partner', 'Friends': 'with_friends',
  'Alone': 'alone', 'Dormitory': 'dormitory'};
const _food = {'Mostly at home': 'home_cooked', 'A mix of both': 'mix', 'Mostly outside': 'mostly_outside'};
const _transport = {
  'Walk': 'walk', 'Bicycle': 'bicycle', 'Motorcycle / Scooter': 'motorcycle',
  'Bus': 'bus', 'Train / Metro': 'train', 'Car': 'car', 'Auto / Cab': 'auto', 'Mixed': 'mixed',
};
const _incomeSources = {'Salary': 'salary', 'Business': 'business', 'Freelance': 'freelance',
  'Scholarship': 'scholarship', 'Part-time': 'part_time', 'Family support': 'family_support'};
const _optimize = {'Maximum savings': 'max_savings', 'Balanced life': 'balanced',
  'Comfort first': 'comfort_first', 'Chase my goal': 'aggressive_goal'};

class _Draft {
  String? country, otherCountry, lifeStage, lifeStageNote, living, livingNote, food, transportMode, transportNote, optimize;
  String foodAmount = '', transportAmount = '', incomeAmount = '', lifestyleAmount = '', rentAmount = '';
  String goalName = '', goalAmount = '';
  String? incomeSource;
  bool scholarship = false, partTime = false;
  String scholarshipAmount = '', partTimeAmount = '';
}

class _BudgetSetupScreenState extends ConsumerState<BudgetSetupScreen> {
  final _d = _Draft();
  int _i = 0;
  bool _busy = false;

  bool get _isStudent =>
      {'high_school', 'ug_student', 'pg_student', 'scholarship_student'}.contains(_d.lifeStage);
  bool get _needsRent => _d.living != null && _d.living != 'with_parents' && _d.living != 'dormitory';

  List<String> get _steps => [
        'intro', 'country', 'life', 'living', 'foodHabit', 'foodAmount', 'transport', 'transportAmt',
        if (_isStudent) 'scholarship',
        if (_isStudent) 'partTime',
        'income', 'lifestyle',
        if (_needsRent) 'rent',
        'goal', 'optimize', 'done',
      ];

  String get _step => _steps[_i.clamp(0, _steps.length - 1)];

  void _next() => setState(() => _i = (_i + 1).clamp(0, _steps.length - 1));
  void _back() => setState(() => _i = (_i - 1).clamp(0, _steps.length - 1));

  String _why() => switch (_step) {
        'intro' => 'Let’s get to know you first, so the plan actually fits your life — not a generic template.',
        'country' => 'Where do you live? It sets local cost baselines and your currency context.',
        'life' => 'Your life stage changes everything — a student isn’t budgeted like a business owner.',
        'living' => 'Who you live with shapes rent and food more than almost anything else.',
        'foodHabit' => 'Food is usually the biggest everyday cost — how do you mostly eat?',
        'foodAmount' => 'Roughly what you spend on food, so I can protect it as an essential.',
        'transport' => 'How you get around tells me what’s essential vs. flexible.',
        'transportAmt' => 'Your typical monthly transport cost.',
        'scholarship' => 'Scholarships count as income — it helps me size your real budget.',
        'partTime' => 'Part-time work is income too. A few hours can change the whole plan.',
        'income' => 'Now the money. What comes in each month — this drives daily limits, buffers and goals.',
        'lifestyle' => 'Fun matters too — games, eating out, shopping. I keep room for it.',
        'rent' => 'Your monthly rent — a protected housing cost.',
        'goal' => 'Saving toward something? Name it and a monthly amount (you can skip this).',
        'optimize' => 'Last one — how should I optimise your plan?',
        _ => 'All set — let me build your plan.',
      };

  @override
  Widget build(BuildContext context) {
    return CompanionScaffold(
      title: 'Get to know you',
      commentary: _why(),
      mood: CompanionMood.neutral,
      child: AbsorbPointer(absorbing: _busy, child: _body()),
    );
  }

  Widget _body() {
    final cur = ref.watch(userSettingsProvider).valueOrNull?.baseCurrency ?? 'INR';
    switch (_step) {
      case 'intro':
        return _pad([
          const Text('A few quick questions — no spreadsheets, I promise. You can change any answer later just by telling me.'),
          const SizedBox(height: 20),
          FilledButton(onPressed: _next, child: const Text("Let's start")),
        ]);
      case 'country':
        return _choice(_countries.keys.toList(),
            current: _countries.entries.where((e) => e.value == _d.country).map((e) => e.key).firstOrNull ?? _d.otherCountry,
            onPick: (label, custom) => setState(() {
              if (custom) { _d.country = null; _d.otherCountry = label; }
              else { _d.country = _countries[label]; _d.otherCountry = null; }
            }),
            enabled: _d.country != null || (_d.otherCountry ?? '').isNotEmpty);
      case 'life':
        return _choice(_lifeStages.keys.toList(),
            current: _lifeStages.entries.where((e) => e.value == _d.lifeStage).map((e) => e.key).firstOrNull ?? _d.lifeStageNote,
            onPick: (label, custom) => setState(() {
              if (custom) { _d.lifeStage = 'other'; _d.lifeStageNote = label; }
              else { _d.lifeStage = _lifeStages[label]; _d.lifeStageNote = null; }
            }),
            enabled: _d.lifeStage != null);
      case 'living':
        return _choice(_living.keys.toList(),
            current: _living.entries.where((e) => e.value == _d.living).map((e) => e.key).firstOrNull ?? _d.livingNote,
            onPick: (label, custom) => setState(() {
              if (custom) { _d.living = 'other'; _d.livingNote = label; }
              else { _d.living = _living[label]; _d.livingNote = null; }
            }),
            enabled: _d.living != null);
      case 'foodHabit':
        return _choice(_food.keys.toList(),
            current: _d.food == 'other' ? 'Other' : _food.entries.where((e) => e.value == _d.food).map((e) => e.key).firstOrNull,
            onPick: (label, custom) => setState(() => _d.food = custom ? 'other' : _food[label]),
            enabled: _d.food != null);
      case 'foodAmount':
        final daily = _d.food != 'home_cooked';
        return _amount(daily ? 'Food per day ($cur)' : 'Groceries per month ($cur)',
            _d.foodAmount, (v) => _d.foodAmount = v);
      case 'transport':
        return _choice(_transport.keys.toList(),
            current: _d.transportMode == 'other'
                ? _d.transportNote
                : _transport.entries.where((e) => e.value == _d.transportMode).map((e) => e.key).firstOrNull,
            onPick: (label, custom) => setState(() {
              if (custom) { _d.transportMode = 'other'; _d.transportNote = label; }
              else { _d.transportMode = _transport[label]; _d.transportNote = null; }
            }),
            enabled: _d.transportMode != null);
      case 'transportAmt':
        return _amount('Transport per month ($cur)', _d.transportAmount, (v) => _d.transportAmount = v, optional: true);
      case 'scholarship':
        return _yesNo(_d.scholarship, (v) => setState(() => _d.scholarship = v),
            amountLabel: 'Scholarship per month ($cur)', amount: _d.scholarshipAmount,
            onAmount: (v) => _d.scholarshipAmount = v);
      case 'partTime':
        return _yesNo(_d.partTime, (v) => setState(() => _d.partTime = v),
            amountLabel: 'Part-time income per month ($cur)', amount: _d.partTimeAmount,
            onAmount: (v) => _d.partTimeAmount = v);
      case 'income':
        final incRaw = _d.incomeAmount.trim();
        return _pad([
          _moneyField('Monthly income ($cur) — leave blank if none', _d.incomeAmount, (v) => setState(() => _d.incomeAmount = v)),
          const SizedBox(height: 16),
          const Text('Where does most of it come from?'),
          const SizedBox(height: 8),
          OtherableChips(
            options: _incomeSources.keys.toList(),
            initialValue: _incomeSources.entries.where((e) => e.value == _d.incomeSource).map((e) => e.key).firstOrNull,
            onChanged: (v, custom) => setState(() => _d.incomeSource = custom ? 'other' : _incomeSources[v]),
          ),
          const SizedBox(height: 20),
          // Income is optional — homemakers, retirees and between-jobs users may
          // have none (or it's captured as scholarship/part-time/family support).
          _nav(enabled: incRaw.isEmpty || double.tryParse(incRaw) != null),
        ]);
      case 'lifestyle':
        return _amount('Fun & lifestyle per month ($cur)', _d.lifestyleAmount,
            (v) => _d.lifestyleAmount = v, optional: true);
      case 'rent':
        return _amount('Rent per month ($cur)', _d.rentAmount, (v) => _d.rentAmount = v, optional: true);
      case 'goal':
        return _pad([
          _moneyField('Goal name (e.g. Japan fund)', _d.goalName, (v) => setState(() => _d.goalName = v), number: false),
          const SizedBox(height: 12),
          _moneyField('Save per month ($cur)', _d.goalAmount, (v) => setState(() => _d.goalAmount = v)),
          const SizedBox(height: 20),
          _nav(enabled: true, skipLabel: 'Skip'),
        ]);
      case 'optimize':
        return _pad([
          OtherableChips(
            options: _optimize.keys.toList(),
            initialValue: _optimize.entries.where((e) => e.value == _d.optimize).map((e) => e.key).firstOrNull,
            onChanged: (v, _) => setState(() => _d.optimize = _optimize[v]),
            otherLabel: 'Not sure',
          ),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _busy ? null : _finish,
            child: _busy
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Build my plan'),
          ),
        ]);
      default:
        return _pad([const Center(child: CircularProgressIndicator())]);
    }
  }

  Future<void> _finish() async {
    final cur = ref.read(userSettingsProvider).valueOrNull?.baseCurrency ?? 'INR';
    setState(() => _busy = true);
    final plan = ref.read(budgetPlanRepositoryProvider);
    final budget = ref.read(budgetRepositoryProvider);
    try {
      final body = <String, dynamic>{
        if (_d.country != null) 'current_country': _d.country,
        if ((_d.otherCountry ?? '').isNotEmpty) 'current_city': _d.otherCountry,
        if (_d.lifeStage != null) 'life_stage': _d.lifeStage,
        if ((_d.lifeStageNote ?? '').isNotEmpty) 'life_stage_note': _d.lifeStageNote,
        if (_d.living != null) 'living_situation': _d.living,
        if ((_d.livingNote ?? '').isNotEmpty) 'living_note': _d.livingNote,
        if (_d.food != null) 'food_situation': _d.food,
        if (_d.optimize != null) 'optimization_style': _d.optimize,
        if (_d.transportMode != null) 'transport_mode': _d.transportMode,
        if ((_d.transportNote ?? '').isNotEmpty) 'transport_note': _d.transportNote,
      };
      final foodAmt = _d.foodAmount.trim();
      if (foodAmt.isNotEmpty) body[_d.food == 'home_cooked' ? 'food_monthly' : 'food_daily'] = foodAmt;
      if (_d.transportAmount.trim().isNotEmpty) body['transport_monthly'] = _d.transportAmount.trim();
      if (_needsRent && _d.rentAmount.trim().isNotEmpty) body['rent_monthly'] = _d.rentAmount.trim();
      if (_d.lifestyleAmount.trim().isNotEmpty) body['lifestyle_monthly'] = _d.lifestyleAmount.trim();
      await plan.patchProfile(body);

      if (double.tryParse(_d.incomeAmount.trim()) != null) {
        await budget.createIncomeSource(
            label: _incomeSources.entries.where((e) => e.value == _d.incomeSource).map((e) => e.key).firstOrNull ?? 'Income',
            sourceType: _d.incomeSource ?? 'other', amount: _d.incomeAmount.trim(), currency: cur);
      }
      if (_d.scholarship && double.tryParse(_d.scholarshipAmount.trim()) != null) {
        await budget.createIncomeSource(label: 'Scholarship', sourceType: 'scholarship', amount: _d.scholarshipAmount.trim(), currency: cur);
      }
      if (_d.partTime && double.tryParse(_d.partTimeAmount.trim()) != null) {
        await budget.createIncomeSource(label: 'Part-time job', sourceType: 'part_time', amount: _d.partTimeAmount.trim(), currency: cur);
      }
      if (_d.goalName.trim().isNotEmpty && double.tryParse(_d.goalAmount.trim()) != null) {
        await budget.createSavingsGoal(name: _d.goalName.trim(), amount: _d.goalAmount.trim(), currency: cur);
      }
      ref.invalidate(profileProvider);
      ref.invalidate(realityProvider);
      ref.invalidate(feasibilityProvider);
      ref.invalidate(recommendationsProvider);
      if (!mounted) return;
      context.go('/profile-summary');   // show what Advary learned, then "Create my plan" → /plan
    } on AppError catch (e) {
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  // --- shared widgets ---
  Widget _pad(List<Widget> children) =>
      ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 32), children: children);

  Widget _choice(List<String> options,
      {required void Function(String, bool) onPick, required bool enabled, String? current,
      bool allowOther = true, String? skipLabel}) {
    final chips = allowOther
        ? OtherableChips(options: options, initialValue: current, onChanged: onPick)
        : Wrap(spacing: 8, runSpacing: 8, children: [
            for (final o in options) ChoiceChip(label: Text(o), selected: current == o, onSelected: (_) => onPick(o, false)),
          ]);
    return _pad([chips, const SizedBox(height: 20), _nav(enabled: enabled, skipLabel: skipLabel)]);
  }

  Widget _amount(String label, String value, ValueChanged<String> onChanged, {bool optional = false}) =>
      _pad([
        _moneyField(label, value, (v) => setState(() => onChanged(v))),
        const SizedBox(height: 20),
        _nav(enabled: optional || double.tryParse(value.trim()) != null, skipLabel: optional ? 'Skip' : null),
      ]);

  Widget _yesNo(bool value, ValueChanged<bool> onChanged,
      {required String amountLabel, required String amount, required ValueChanged<String> onAmount}) {
    return _pad([
      Wrap(spacing: 8, children: [
        ChoiceChip(label: const Text('Yes'), selected: value, onSelected: (_) => onChanged(true)),
        ChoiceChip(label: const Text('No'), selected: !value, onSelected: (_) => onChanged(false)),
      ]),
      if (value) ...[
        const SizedBox(height: 16),
        _moneyField(amountLabel, amount, (v) => setState(() => onAmount(v))),
      ],
      const SizedBox(height: 20),
      _nav(enabled: !value || double.tryParse(amount.trim()) != null, skipLabel: 'Skip'),
    ]);
  }

  Widget _moneyField(String label, String value, ValueChanged<String> onChanged, {bool number = true}) => TextField(
        keyboardType: number ? const TextInputType.numberWithOptions(decimal: true) : TextInputType.text,
        inputFormatters: number ? [FilteringTextInputFormatter.allow(RegExp(r'[0-9.]'))] : null,
        decoration: InputDecoration(labelText: label),
        controller: TextEditingController(text: value)..selection = TextSelection.collapsed(offset: value.length),
        onChanged: onChanged,
      );

  Widget _nav({required bool enabled, String? skipLabel}) => Row(
        children: [
          if (_i > 0) ...[
            Expanded(child: OutlinedButton(onPressed: _back, child: const Text('Back'))),
            const SizedBox(width: 12),
          ],
          if (skipLabel != null) ...[
            Expanded(child: TextButton(onPressed: _next, child: Text(skipLabel))),
            const SizedBox(width: 12),
          ],
          Expanded(child: FilledButton(onPressed: enabled ? _next : null, child: const Text('Next'))),
        ],
      );
}
