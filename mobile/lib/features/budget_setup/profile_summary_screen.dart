import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/budget/budget_plan_repository.dart';
import '../../core/companion/companion_orb.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/settings/settings_repository.dart';
import '../../core/theme/glass.dart';

const _countryName = {'IN': 'India', 'JP': 'Japan', 'US': 'United States', 'GB': 'the UK'};
const _lifeStage = {
  'middle_school': 'Middle-school student', 'high_school': 'High-school student',
  'ug_student': 'UG Student', 'pg_student': 'PG Student', 'scholarship_student': 'Scholarship student',
  'working_professional': 'Working professional', 'self_employed': 'Self-employed', 'business_owner': 'Business owner',
};
const _living = {'with_parents': 'Lives with parents', 'with_partner': 'Lives with partner',
  'with_friends': 'Lives with friends', 'alone': 'Lives independently', 'dormitory': 'Lives in a dorm'};
const _food = {'home_cooked': 'Mostly cooks at home', 'mostly_outside': 'Mostly eats out', 'mix': 'Mix of home & outside'};
const _optimize = {'max_savings': 'Maximum savings', 'balanced': 'Balanced life',
  'comfort_first': 'Comfort first', 'aggressive_goal': 'Chasing the goal'};
const _source = {'salary': 'Salary', 'business': 'Business', 'freelance': 'Freelance',
  'scholarship': 'Scholarship', 'part_time': 'Part-time work', 'family_support': 'Family support', 'pension': 'Pension'};

class ProfileSummaryScreen extends ConsumerWidget {
  const ProfileSummaryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(profileProvider);
    final reality = ref.watch(realityProvider);
    final companion = (ref.watch(userSettingsProvider).valueOrNull?.companionName?.isNotEmpty ?? false)
        ? ref.watch(userSettingsProvider).valueOrNull!.companionName!
        : 'Advary';
    return CompanionScaffold(
      title: 'About you',
      commentary: 'Here’s what I understand so far — check it, then I’ll build your plan.',
      child: profile.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(e is AppError ? e.message : 'I couldn’t load your profile just now.',
                    textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyMedium),
                const SizedBox(height: 12),
                FilledButton.tonal(
                    onPressed: () {
                      ref.invalidate(profileProvider);
                      ref.invalidate(realityProvider);
                    },
                    child: const Text('Try again')),
              ],
            ),
          ),
        ),
        data: (p) => ListView(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 32),
          children: [
            GlassCard(
              child: Row(children: [
                const CompanionOrb(state: OrbState.celebrating, size: 52),
                const SizedBox(width: 12),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('$companion’s understanding of you',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 4),
                  Text('You can change any of this anytime — just tell me.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
                ])),
              ]),
            ),
            const SizedBox(height: 14),
            _facts(context, p),
            const SizedBox(height: 14),
            reality.when(
              loading: () => const SizedBox.shrink(),
              error: (_, __) => const SizedBox.shrink(),
              data: (r) => _incomeAndGoals(context, r),
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: () => context.go('/plan'),
              icon: const Icon(Icons.insights_outlined),
              label: const Text('Create my plan'),
            ),
            const SizedBox(height: 8),
            TextButton(onPressed: () => context.go('/budget-setup'), child: const Text('Edit my answers')),
          ],
        ),
      ),
    );
  }

  Widget _facts(BuildContext context, Map<String, dynamic> p) {
    final rows = <(IconData, String)>[];
    final ls = p['life_stage']?.toString();
    if (ls != null) rows.add((Icons.school_outlined, _lifeStage[ls] ?? p['life_stage_note']?.toString() ?? ls));
    final cc = p['current_country']?.toString();
    final city = p['current_city']?.toString();
    if (cc != null || city != null) {
      rows.add((Icons.place_outlined, [if (city != null) city, if (cc != null) _countryName[cc] ?? cc].join(', ')));
    }
    if (p['moving_country'] == true && p['future_country'] != null) {
      final yr = p['future_move_year'];
      rows.add((Icons.flight_takeoff, 'Moving to ${_countryName[p['future_country']] ?? p['future_country']}'
          '${yr != null ? ' in $yr' : ''}'));
    }
    final living = p['living_situation']?.toString();
    if (living != null) rows.add((Icons.home_outlined, _living[living] ?? living));
    final food = p['food_situation']?.toString();
    if (food != null) rows.add((Icons.restaurant_outlined, _food[food] ?? food));
    final opt = p['optimization_style']?.toString();
    if (opt != null) rows.add((Icons.tune, 'Planning style: ${_optimize[opt] ?? opt}'));

    if (rows.isEmpty) {
      return const GlassCard(child: Text('I don’t know much yet — tell me about yourself and I’ll learn.'));
    }
    return GlassCard(
      child: Column(children: [
        for (final r in rows)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 7),
            child: Row(children: [
              Icon(r.$1, size: 20, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 12),
              Expanded(child: Text(r.$2, style: Theme.of(context).textTheme.bodyLarge)),
            ]),
          ),
      ]),
    );
  }

  Widget _incomeAndGoals(BuildContext context, Reality r) {
    final tt = Theme.of(context).textTheme;
    String money(double v) => '${r.currency} ${v.toStringAsFixed(0)}';
    return GlassCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (r.incomeSources.isNotEmpty) ...[
          Text('Income (${money(r.incomeTotal)}/mo)', style: tt.titleSmall),
          const SizedBox(height: 8),
          for (final s in r.incomeSources)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(children: [
                const Icon(Icons.account_balance_wallet_outlined, size: 18),
                const SizedBox(width: 10),
                Expanded(child: Text('${s.label}  ·  ${_source[s.sourceType] ?? s.sourceType}', style: tt.bodyMedium)),
                Text(money(s.monthly), style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
              ]),
            ),
        ],
        if (r.goals.isNotEmpty) ...[
          const SizedBox(height: 12),
          Text('Goals', style: tt.titleSmall),
          const SizedBox(height: 6),
          for (final g in r.goals)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(children: [
                const Icon(Icons.flag_outlined, size: 18, color: Color(0xFF34D399)),
                const SizedBox(width: 10),
                Expanded(child: Text(g, style: tt.bodyMedium)),
              ]),
            ),
        ],
      ]),
    );
  }
}
