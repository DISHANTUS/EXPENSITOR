import 'dart:async';

import 'package:expensitor_mobile/core/theme/app_theme.dart';
import 'package:expensitor_mobile/features/home/daily_report_repository.dart';
import 'package:expensitor_mobile/features/home/widgets/daily_report_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

DailyReport _report({
  bool dayDone = true,
  String saved = '847.74',
  String status = 'under',
  int streak = 0,
  ReportGoal? goal,
  List<String> lines = const ['You came in INR 847.74 under your INR 967.74 allowance today.'],
}) =>
    DailyReport(
      date: '2026-07-16',
      currency: 'INR',
      dayDone: dayDone,
      dailyAllowance: '967.74',
      spentToday: '120.00',
      savedToday: saved,
      status: status,
      streakDays: streak,
      windowDays: 4,
      windowNet: '800.97',
      goal: goal,
      lines: lines,
    );

Future<void> _pump(WidgetTester tester, DailyReport? report) async {
  await tester.pumpWidget(ProviderScope(
    overrides: [
      if (report != null)
        dailyReportProvider.overrideWith((ref) async => report)
      else
        // Never resolves: stands in for "still loading".
        dailyReportProvider.overrideWith((ref) => Completer<DailyReport>().future),
    ],
    child: MaterialApp(theme: AppTheme.dark(), home: const Scaffold(body: DailyReportCard())),
  ));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('a finished day is reported as finished', (tester) async {
    await _pump(tester, _report(dayDone: true));
    expect(find.text('How today went'), findsOneWidget);
    expect(find.textContaining('under your INR 967.74 allowance'), findsOneWidget);
  });

  testWidgets('a day still in progress is never called a wrap-up', (tester) async {
    // The heading must not imply the day is done — the user can still spend.
    await _pump(tester, _report(
      dayDone: false,
      lines: const ["So far you're INR 847.74 under your INR 967.74 allowance for today."],
    ));
    expect(find.text('Today so far'), findsOneWidget);
    expect(find.text('How today went'), findsNothing);
  });

  testWidgets('the card shows nothing at all until it has something true to say', (tester) async {
    await _pump(tester, null);
    expect(find.byType(SizedBox), findsWidgets);
    expect(find.text('How today went'), findsNothing);
    expect(find.text('Today so far'), findsNothing);
  });

  testWidgets('an empty report renders nothing rather than an empty card', (tester) async {
    await _pump(tester, _report(lines: const []));
    expect(find.text('How today went'), findsNothing);
  });

  // Two separate tests, not one with two pumps: re-pumping reuses the same
  // ProviderScope element, so the second override never takes effect.
  testWidgets('a single day is not badged as a run', (tester) async {
    await _pump(tester, _report(streak: 1));
    expect(find.textContaining('day run'), findsNothing);
  });

  testWidgets('a real run is badged', (tester) async {
    await _pump(tester, _report(streak: 3));
    expect(find.text('3 day run'), findsOneWidget);
  });

  testWidgets('the goal bar agrees with the numbers printed above it', (tester) async {
    // 3000 target, 1200 left => 60% there. If the bar and the text disagree,
    // the user is looking at two different stories about one goal.
    await _pump(tester, _report(
      goal: const ReportGoal(id: 'g1', name: 'Headphones', targetAmount: '3000', remaining: '1200', daysLeft: 30),
      lines: const ['Still INR 1,200 to go for Headphones, 30 days out.'],
    ));

    expect(find.text('Headphones · 60% there'), findsOneWidget);
    final bar = tester.widget<LinearProgressIndicator>(find.byType(LinearProgressIndicator));
    expect(bar.value, closeTo(0.6, 0.001));
  });

  testWidgets('a finished goal gets no progress bar to nag with', (tester) async {
    await _pump(tester, _report(
      goal: const ReportGoal(id: 'g1', name: 'Headphones', targetAmount: '3000', remaining: '0'),
      lines: const ["You've already got what you need for Headphones."],
    ));
    expect(find.byType(LinearProgressIndicator), findsNothing);
    expect(find.textContaining('already got what you need'), findsOneWidget);
  });

  testWidgets('with no goal there is no bar', (tester) async {
    await _pump(tester, _report());
    expect(find.byType(LinearProgressIndicator), findsNothing);
  });

  testWidgets('being over budget is shown, not softened away', (tester) async {
    await _pump(tester, _report(
      saved: '-250',
      status: 'over',
      lines: const ["You're INR 250 over your INR 967.74 allowance today."],
    ));
    expect(find.textContaining('over your'), findsOneWidget);
  });

  testWidgets('a nonsense target never divides by zero', (tester) async {
    await _pump(tester, _report(
      goal: const ReportGoal(id: 'g1', name: 'Odd', targetAmount: '0', remaining: '5'),
      lines: const ['Still INR 5 to go for Odd.'],
    ));
    expect(tester.takeException(), isNull);
    expect(find.byType(LinearProgressIndicator), findsNothing);
  });
}
