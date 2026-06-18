// Calendar DTOs. Markers are rendered from a backend-driven registry (icon/
// color/title), so Sprint 4 can add marker types server-side with no client
// rewrite. All money is base-currency strings (formatted via money.dart).

import 'package:flutter/material.dart';

String? _s(dynamic v) => v?.toString();

Color _hexColor(String? hex) {
  if (hex == null || !hex.startsWith('#') || hex.length < 7) return const Color(0xFF1E6F5C);
  return Color(int.parse('FF${hex.substring(1, 7)}', radix: 16));
}

class CalendarMarkerType {
  const CalendarMarkerType({
    required this.key,
    required this.icon,
    required this.color,
    required this.title,
    required this.category,
  });

  factory CalendarMarkerType.fromJson(Map<String, dynamic> j) => CalendarMarkerType(
        key: _s(j['key']) ?? '',
        icon: _s(j['icon']) ?? '•',
        color: _hexColor(_s(j['color'])),
        title: _s(j['title']) ?? '',
        category: _s(j['category']) ?? '',
      );

  final String key;
  final String icon; // emoji
  final Color color;
  final String title;
  final String category;
}

/// Minimal built-in registry so the calendar still renders if the catalog fetch
/// fails. The backend remains the source of truth for the full set.
const fallbackMarkers = <String, CalendarMarkerType>{
  'budget_over': CalendarMarkerType(key: 'budget_over', icon: '🔴', color: Color(0xFFE53935), title: 'Over budget', category: 'budget'),
  'budget_saved': CalendarMarkerType(key: 'budget_saved', icon: '👑', color: Color(0xFFFBC02D), title: 'Saved money', category: 'budget'),
  'budget_within': CalendarMarkerType(key: 'budget_within', icon: '🟢', color: Color(0xFF43A047), title: 'Within budget', category: 'budget'),
  'income': CalendarMarkerType(key: 'income', icon: '💼', color: Color(0xFF1E88E5), title: 'Income', category: 'income'),
  'event': CalendarMarkerType(key: 'event', icon: '📅', color: Color(0xFF7E57C2), title: 'Planned event', category: 'planning'),
};

class DayCell {
  const DayCell({
    required this.date,
    required this.spent,
    required this.income,
    required this.eventCount,
    required this.classification,
    required this.markers,
    this.plannedBudget,
    this.effectiveBudget,
  });

  factory DayCell.fromJson(Map<String, dynamic> j) => DayCell(
        date: DateTime.parse(j['date'].toString()),
        spent: _s(j['spent']) ?? '0',
        income: _s(j['income']) ?? '0',
        eventCount: (j['event_count'] as num?)?.toInt() ?? 0,
        classification: _s(j['classification']) ?? 'none',
        markers: ((j['markers'] as List?) ?? const []).map((e) => e.toString()).toList(),
        plannedBudget: _s(j['planned_budget']),
        effectiveBudget: _s(j['effective_budget']),
      );

  final DateTime date;
  final String spent;
  final String income;
  final int eventCount;
  final String classification;
  final List<String> markers;
  final String? plannedBudget;
  final String? effectiveBudget;
}

class MonthView {
  const MonthView({required this.year, required this.month, required this.currency, required this.byDay});

  factory MonthView.fromJson(Map<String, dynamic> j) {
    final days = ((j['days'] as List?) ?? const [])
        .whereType<Map>()
        .map((e) => DayCell.fromJson(e.cast<String, dynamic>()));
    return MonthView(
      year: (j['year'] as num?)?.toInt() ?? 0,
      month: (j['month'] as num?)?.toInt() ?? 0,
      currency: _s(j['base_currency']) ?? 'INR',
      byDay: {for (final d in days) DateTime(d.date.year, d.date.month, d.date.day): d},
    );
  }

  final int year;
  final int month;
  final String currency;
  final Map<DateTime, DayCell> byDay;

  DayCell? cell(DateTime day) => byDay[DateTime(day.year, day.month, day.day)];
}

class DayLine {
  const DayLine({required this.title, required this.amount, required this.currency, this.tag});
  final String title;
  final String amount;
  final String currency;
  final String? tag;
}

class DayDetail {
  const DayDetail({
    required this.date,
    required this.currency,
    required this.spent,
    required this.income,
    required this.classification,
    required this.markers,
    required this.expenses,
    required this.incomes,
    required this.events,
    this.plannedBudget,
    this.effectiveBudget,
    this.remaining,
    this.overspendReason,
  });

  factory DayDetail.fromJson(Map<String, dynamic> j) {
    final cur = _s(j['base_currency']) ?? 'INR';
    List<DayLine> lines(String key, DayLine Function(Map<String, dynamic>) f) =>
        ((j[key] as List?) ?? const []).whereType<Map>().map((e) => f(e.cast<String, dynamic>())).toList();
    return DayDetail(
      date: DateTime.parse(j['date'].toString()),
      currency: cur,
      spent: _s(j['spent']) ?? '0',
      income: _s(j['income']) ?? '0',
      classification: _s(j['classification']) ?? 'none',
      markers: ((j['markers'] as List?) ?? const []).map((e) => e.toString()).toList(),
      plannedBudget: _s(j['planned_budget']),
      effectiveBudget: _s(j['effective_budget']),
      remaining: _s(j['remaining']),
      overspendReason: _s(j['overspend_reason']),
      expenses: lines('expenses', (e) => DayLine(
            title: (_s(e['description'])?.isNotEmpty ?? false) ? _s(e['description'])! : 'Expense',
            amount: _s(e['converted_amount']) ?? '0',
            currency: _s(e['base_currency']) ?? cur,
          )),
      incomes: lines('incomes', (e) => DayLine(
            title: (_s(e['description'])?.isNotEmpty ?? false) ? _s(e['description'])! : (_s(e['source_type']) ?? 'Income'),
            amount: _s(e['converted_amount']) ?? '0',
            currency: _s(e['base_currency']) ?? cur,
            tag: _s(e['source_type']),
          )),
      events: lines('events', (e) => DayLine(
            title: _s(e['title']) ?? 'Event',
            amount: _s(e['converted_amount']) ?? '0',
            currency: _s(e['base_currency']) ?? cur,
            tag: _s(e['occasion_type']),
          )),
    );
  }

  final DateTime date;
  final String currency;
  final String spent;
  final String income;
  final String classification;
  final List<String> markers;
  final String? plannedBudget;
  final String? effectiveBudget;
  final String? remaining;
  final String? overspendReason;
  final List<DayLine> expenses;
  final List<DayLine> incomes;
  final List<DayLine> events;
}
