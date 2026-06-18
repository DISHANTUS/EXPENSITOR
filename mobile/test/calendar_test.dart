import 'package:expensitor_mobile/core/companion/companion_mood.dart';
import 'package:expensitor_mobile/core/companion/greeting.dart';
import 'package:expensitor_mobile/features/calendar/calendar_models.dart';
import 'package:expensitor_mobile/features/date_details/date_details_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('CalendarMarkerType parses hex color', () {
    final m = CalendarMarkerType.fromJson(
        {'key': 'budget_over', 'icon': '🔴', 'color': '#E53935', 'title': 'Over budget', 'category': 'budget'});
    expect(m.icon, '🔴');
    expect(m.color, const Color(0xFFE53935));
    expect(m.category, 'budget');
  });

  test('DayCell parses markers + classification + budgets', () {
    final c = DayCell.fromJson({
      'date': '2026-06-16',
      'spent': '2300.0000',
      'income': '0',
      'event_count': 0,
      'planned_budget': '1500.0000',
      'effective_budget': '1500.0000',
      'classification': 'over',
      'markers': ['budget_over'],
    });
    expect(c.date, DateTime(2026, 6, 16));
    expect(c.classification, 'over');
    expect(c.markers, ['budget_over']);
    expect(c.effectiveBudget, '1500.0000');
  });

  test('MonthView indexes days for lookup', () {
    final m = MonthView.fromJson({
      'year': 2026, 'month': 6, 'base_currency': 'INR',
      'days': [
        {'date': '2026-06-16', 'spent': '300', 'income': '0', 'event_count': 1,
         'planned_budget': '1000', 'effective_budget': '1000', 'classification': 'saved',
         'markers': ['budget_saved', 'event']},
      ],
    });
    final cell = m.cell(DateTime(2026, 6, 16));
    expect(cell, isNotNull);
    expect(cell!.markers, contains('event'));
    expect(m.cell(DateTime(2026, 6, 17)), isNull);
  });

  test('DayDetail parses lines + remaining', () {
    final d = DayDetail.fromJson({
      'date': '2026-06-16', 'base_currency': 'INR',
      'planned_budget': '1500', 'effective_budget': '1500',
      'spent': '2300', 'income': '5000', 'remaining': '-800',
      'classification': 'over', 'markers': ['budget_over'], 'overspend_reason': 'gadget',
      'expenses': [{'converted_amount': '2300', 'base_currency': 'INR', 'description': 'Phone'}],
      'incomes': [{'converted_amount': '5000', 'base_currency': 'INR', 'source_type': 'salary'}],
      'events': [{'converted_amount': '500', 'base_currency': 'INR', 'title': 'Dinner', 'occasion_type': 'outing'}],
    });
    expect(d.remaining, '-800');
    expect(d.overspendReason, 'gadget');
    expect(d.expenses.single.title, 'Phone');
    expect(d.incomes.single.tag, 'salary');
    expect(d.events.single.title, 'Dinner');
  });

  group('dayCommentary', () {
    final today = DateTime(2026, 6, 16);
    DayDetail make({required String cls, String spent = '0', String? budget, List<DayLine> events = const []}) =>
        DayDetail(
          date: today, currency: 'INR', spent: spent, income: '0', classification: cls,
          markers: const [], expenses: const [], incomes: const [], events: events,
          effectiveBudget: budget,
        );

    test('over mentions going over', () {
      final line = dayCommentary(make(cls: 'over', spent: '2300', budget: '1500'), today);
      expect(line.toLowerCase(), contains('over budget'));
    });
    test('saved is encouraging', () {
      final line = dayCommentary(make(cls: 'saved', spent: '300', budget: '1000'), today);
      expect(line.toLowerCase(), contains('saved'));
    });
    test('future day with event', () {
      final fut = DateTime(2026, 6, 20);
      final d = DayDetail(
        date: fut, currency: 'INR', spent: '0', income: '0', classification: 'none',
        markers: const [], expenses: const [], incomes: const [],
        events: const [DayLine(title: 'Trip', amount: '0', currency: 'INR')],
      );
      expect(dayCommentary(d, today).toLowerCase(), contains('planned'));
    });
  });

  group('timeGreeting', () {
    test('varies by time of day', () {
      expect(timeGreeting(DateTime(2026, 6, 17, 8)), startsWith('Good morning'));
      expect(timeGreeting(DateTime(2026, 6, 17, 14)), startsWith('Good afternoon'));
      expect(timeGreeting(DateTime(2026, 6, 17, 19)), startsWith('Good evening'));
      expect(timeGreeting(DateTime(2026, 6, 17, 23)), startsWith('Good evening'));
    });
  });

  group('companion mood', () {
    test('from classification', () {
      expect(moodFromClassification('over'), CompanionMood.concerned);
      expect(moodFromClassification('saved'), CompanionMood.happy);
      expect(moodFromClassification('none'), CompanionMood.neutral);
    });
    test('from severity', () {
      expect(moodFromSeverity('alert'), CompanionMood.concerned);
      expect(moodFromSeverity('success'), CompanionMood.happy);
      expect(moodFromSeverity(null), CompanionMood.neutral);
    });
  });
}
