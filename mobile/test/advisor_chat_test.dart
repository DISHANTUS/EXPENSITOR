import 'package:expensitor_mobile/features/advisor/chat_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('ChatTurn parses a report turn (graph + summary + story + follow-ups + session)', () {
    final t = ChatTurn.fromJson({
      'type': 'report',
      'report': {
        'kind': 'week', 'period_label': '7 Jun–13 Jun', 'currency': 'INR', 'confidence': 'medium',
        'series': {
          'granularity': 'day',
          'points': [
            {'label': '7 Jun', 'spent': '300', 'income': '0', 'saved': '0'},
            {'label': '8 Jun', 'spent': '450', 'income': '5000', 'saved': '50'},
          ],
        },
        'summary': {'currency': 'INR', 'total_spent': '750', 'total_income': '5000', 'saved': '50',
                    'red_days': 1, 'crown_days': 2},
        'story': {'beginning': 'b', 'middle': 'm', 'end': 'e'},
        'timeline_events': [{'date': '2026-06-08', 'label': 'Started Japan Fund', 'kind': 'goal'}],
      },
      'follow_ups': [{'label': 'Last month', 'message': 'last month report'}],
      'session': {'last_kind': 'week', 'last_ref': 'this'},
    });
    expect(t.type, 'report');
    expect(t.report!.summary.totalSpent, '750');
    expect(t.report!.series.points.length, 2);
    expect(t.report!.story.middle, 'm');
    expect(t.report!.timelineEvents.single.label, 'Started Japan Fund');
    expect(t.followUps.single.message, 'last month report');
    expect(t.session!.toJson()['last_kind'], 'week');
  });

  test('ChatTurn parses a clarify turn with options', () {
    final t = ChatTurn.fromJson({
      'type': 'clarify', 'message': 'Which report?',
      'options': [{'label': 'Weekly', 'message': 'weekly report'}, {'label': 'Monthly', 'message': 'monthly report'}],
    });
    expect(t.type, 'clarify');
    expect(t.options.map((o) => o.label), containsAll(['Weekly', 'Monthly']));
    expect(t.report, isNull);
  });

  test('ChatTurn parses a drilldown turn', () {
    final t = ChatTurn.fromJson({
      'type': 'drilldown',
      'drilldown': {
        'kind': 'red_days', 'title': 'Red days', 'currency': 'INR', 'explanation': '2 over-budget day(s).',
        'items': [
          {'label': '16 Jun', 'amount': '2300', 'currency': 'INR', 'when': '2026-06-16', 'subtitle': 'gadget'},
        ],
      },
      'follow_ups': [{'label': 'Crown days', 'message': 'show crown days'}],
    });
    expect(t.type, 'drilldown');
    expect(t.drilldown!.title, 'Red days');
    expect(t.drilldown!.items.single.subtitle, 'gadget');
    expect(t.followUps.single.message, 'show crown days');
  });

  test('ChatTurn parses a comparison (report with delta)', () {
    final t = ChatTurn.fromJson({
      'type': 'comparison',
      'report': {
        'kind': 'month', 'period_label': 'June 2026', 'currency': 'INR', 'confidence': 'medium',
        'series': {'granularity': 'week', 'points': []},
        'summary': {'currency': 'INR', 'total_spent': '5000', 'total_income': '0', 'saved': '0', 'red_days': 1, 'crown_days': 0},
        'story': {'beginning': 'Compared to May 2026, …', 'middle': 'Travel rose 40%.', 'end': 'Savings dropped.'},
        'timeline_events': [],
        'comparison_from': '2026-05-01', 'comparison_to': '2026-05-31',
        'delta': {
          'spent_change_pct': 25.0, 'income_change_pct': null, 'saved_change_pct': -10.0,
          'biggest_increase': {'label': 'Travel', 'current': '2000', 'previous': '1000', 'change_pct': 100.0},
          'categories': [{'label': 'Travel', 'current': '2000', 'previous': '1000', 'change_pct': 100.0}],
        },
      },
    });
    expect(t.type, 'comparison');
    expect(t.report!.delta!.spentPct, 25.0);
    expect(t.report!.delta!.biggestIncrease!.label, 'Travel');
    expect(t.report!.comparisonLabel, contains('2026-05-01'));
  });

  test('ChatTurn parses an answer turn', () {
    final t = ChatTurn.fromJson({'type': 'answer', 'message': 'I don’t have enough data yet.'});
    expect(t.type, 'answer');
    expect(t.message, contains('enough'));
  });

  test('ChatTurn carries explain_ref + confidence (advisory)', () {
    final t = ChatTurn.fromJson({
      'type': 'advisory', 'message': 'Ravi still has ₹5,000 outstanding…',
      'explain_ref': 'relationship:Ravi', 'confidence': 'high',
    });
    expect(t.type, 'advisory');
    expect(t.explainRef, 'relationship:Ravi');
    expect(t.confidence, 'high');
  });

  test('ChatTurn parses a forecast turn (paths + evidence + opportunity + levers + future me)', () {
    final t = ChatTurn.fromJson({
      'type': 'forecast',
      'forecast': {
        'kind': 'goal', 'headline': 'March 2028', 'currency': 'INR', 'confidence': 'medium',
        'confidence_word': 'often', 'confidence_note': 'Based on 45 days of history.',
        'reasoning': 'Based on your savings rate of ₹4,500/month…',
        'scenarios': [
          {'mode': 'current', 'label': 'Current Path', 'eta': '2028-03-28', 'monthly_rate': '4500', 'narrative': 'You keep your habits.'},
          {'mode': 'optimistic', 'label': 'Optimistic Path', 'eta': '2027-12-28', 'monthly_rate': '6000', 'narrative': 'You trim food a little.'},
          {'mode': 'conservative', 'label': 'Conservative Path', 'eta': null, 'monthly_rate': '-200', 'narrative': 'Spending creeps up.'},
        ],
        'evidence': [{'label': 'Current savings rate', 'value': '₹4,500/month'}, {'label': 'Goal amount', 'value': '₹300,000'}],
        'opportunity_costs': [{'lever_label': 'Cancel Netflix', 'annual_savings': '6000.00', 'days_earlier': 11, 'summary': 'Netflix: saves ₹6,000/yr — goal arrives 11 days earlier.'}],
        'story': {'beginning': 'b', 'middle': 'm', 'end': 'e'},
        'levers': [{'label': 'Food −10%', 'ref': 'category:Food:-10'}, {'label': 'Save +2000', 'ref': 'save:+2000'}],
        'applied_levers': [{'label': 'Save +1000', 'ref': 'save:+1000'}],
        'timeline_candidates': [{'label': 'Forecasted Japan completion', 'date': '2028-03-28', 'kind': 'forecast'}],
        'goals': [{'id': 'g1', 'name': 'Japan Fund', 'eta': '2028-03-28', 'progress_pct': 25.0}],
        'future_me': {
          'current_path': {'mode': 'current', 'label': 'Current Path', 'eta': '2028-03-28', 'monthly_rate': '4500', 'narrative': 'x'},
          'optimistic_path': {'mode': 'optimistic', 'label': 'Optimistic Path', 'eta': '2027-12-28', 'monthly_rate': '6000', 'narrative': 'y'},
          'conservative_path': {'mode': 'conservative', 'label': 'Conservative Path', 'eta': null, 'monthly_rate': '-200', 'narrative': 'z'},
        },
        'follow_ups': [{'label': 'Show Future Me', 'message': 'show future me'}],
        'explain_ref': 'category:Food',
      },
    });
    expect(t.type, 'forecast');
    final f = t.forecast!;
    expect(f.headline, 'March 2028');
    expect(f.scenarios.length, 3);
    expect(f.scenarios.last.eta, isNull); // honesty: no fabricated date on the negative path
    expect(f.opportunityCosts.single.daysEarlier, 11);
    expect(f.levers.map((l) => l.ref), contains('save:+2000'));
    expect(f.appliedLevers.single.ref, 'save:+1000');
    expect(f.futureMe!.optimisticPath!.monthlyRate, '6000');
    expect(f.goals.single.name, 'Japan Fund');
  });

  test('ChatTurn parses a follow_up turn (check-in with options)', () {
    final t = ChatTurn.fromJson({
      'type': 'follow_up',
      'follow_up': {
        'id': 'a1', 'kind': 'forecast', 'importance': 'high', 'subject_label': 'Japan Fund',
        'claim': 'reach Japan Fund around March 2028',
        'question': 'Last time we talked about reaching Japan Fund. How is it going?',
        'options': [
          {'label': 'Yes', 'value': 'yes'},
          {'label': 'Partially', 'value': 'partial'},
          {'label': 'No', 'value': 'no'},
        ],
      },
    });
    expect(t.type, 'follow_up');
    expect(t.followUp!.subjectLabel, 'Japan Fund');
    expect(t.followUp!.options.map((o) => o.value), ['yes', 'partial', 'no']);
  });

  test('FollowUpAck parses acknowledgement + lesson suggestion', () {
    final a = FollowUpAck.fromJson({
      'acknowledged': 'Thanks for telling me — a one-off.',
      'circumstance': 'unexpected_expense',
      'advice_id': 'a1',
      'lesson_suggestion': 'An emergency buffer may help.',
    });
    expect(a.circumstance, 'unexpected_expense');
    expect(a.lessonSuggestion, contains('buffer'));
  });

  test('ChatTurn parses a recap turn (financial identity + lessons + achievements)', () {
    final t = ChatTurn.fromJson({
      'type': 'recap',
      'recap': {
        'financial_identity': {
          'focus_areas': ['Japan Fund'], 'strongest_habit': 'Consistent goal saving',
          'current_challenge': 'Food spending', 'currency': 'INR',
        },
        'goals': [{'name': 'Japan Fund', 'target': '300000', 'currency': 'INR'}],
        'habits': ['Regular expense logging'],
        'relationships': [{'name': 'Ravi', 'loans': 2, 'repaid': 1}],
        'lessons': [{'id': 'l1', 'lesson': 'Keep an emergency buffer', 'category': 'emergency_fund',
                     'source': 'user_taught', 'occurrences': 3, 'confidence': 'high', 'status': 'confirmed',
                     'importance': 'high', 'times_surfaced': 2, 'times_helpful': 1,
                     'first_observed': '2026-01-01', 'last_observed': '2026-06-01'}],
        'achievements': [{'type': 'goal_completed', 'importance': 'life_milestone', 'label': 'Completed your X goal'}],
        'preferences': {'base_currency': 'INR'},
      },
    });
    expect(t.type, 'recap');
    expect(t.recap!.financialIdentity.focusAreas, ['Japan Fund']);
    expect(t.recap!.financialIdentity.currentChallenge, 'Food spending');
    expect(t.recap!.lessons.single.confidence, 'high');
    expect(t.recap!.achievements.single.type, 'goal_completed');
  });

  test('ChatTurn parses a reflection turn + forecast carries surfaced lesson', () {
    final refl = ChatTurn.fromJson({
      'type': 'reflection',
      'reflection': {'trigger': 'goal_progress', 'importance': 'high',
        'question': 'You saved ₹3,000 more — what helped most?',
        'options': [{'label': 'Better planning', 'value': 'better_planning'}]},
    });
    expect(refl.type, 'reflection');
    expect(refl.reflection!.options.single.value, 'better_planning');

    final fc = ChatTurn.fromJson({
      'type': 'forecast',
      'forecast': {'kind': 'life_event', 'headline': 'Yes', 'currency': 'INR', 'confidence': 'medium',
        'reasoning': 'x', 'surfaced_lesson': 'A lesson you’ve taught me before: keep an emergency buffer.',
        'accuracy_note': 'Of 12 resolved forecasts, 9 were accurate.'},
    });
    expect(fc.forecast!.surfacedLesson, contains('emergency buffer'));
    expect(fc.forecast!.accuracyNote, contains('accurate'));
  });

  test('Explanation parses claim + evidence + why-it-matters', () {
    final e = Explanation.fromJson({
      'claim': 'Ravi still has ₹5,000 outstanding…',
      'confidence': 'medium', 'confidence_word': 'often',
      'reasoning': 'Based on repayment history.',
      'why_it_matters': 'Harder to track who owes what.',
      'evidence': [
        {'label': 'Loans', 'value': '2'},
        {'label': 'Late repayments', 'value': '1'},
        {'label': 'Outstanding', 'value': '₹5,000'},
      ],
    });
    expect(e.confidenceWord, 'often');
    expect(e.whyItMatters, contains('track'));
    expect(e.evidence.length, 3);
    expect(e.evidence.first.value, '2');
  });
}
