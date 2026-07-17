import 'package:expensitor_mobile/core/theme/app_theme.dart';
import 'package:expensitor_mobile/features/budget_setup/festival_card.dart';
import 'package:expensitor_mobile/features/budget_setup/festival_repository.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> _pump(WidgetTester tester, Festivals f, {void Function(String)? onPlan}) async {
  await tester.pumpWidget(ProviderScope(
    overrides: [festivalsProvider.overrideWith((ref) async => f)],
    child: MaterialApp(
      theme: AppTheme.dark(),
      home: Scaffold(body: FestivalCard(onPlan: onPlan)),
    ),
  ));
  await tester.pumpAndSettle();
}

const _diwali = UpcomingFestival(
  name: 'Diwali',
  date: '2026-11-08',
  daysAway: 114,
  line: 'Diwali is in 114 days. Last time, that stretch cost you INR 4,200 more than your usual 15 days.',
  extra: 4200,
);

const _bareDiwali = UpcomingFestival(
  name: 'Diwali',
  date: '2026-11-08',
  daysAway: 114,
  line: 'Diwali is in 114 days.',
);

void main() {
  testWidgets('it shows the next festival in the backend\'s own words', (tester) async {
    await _pump(tester, const Festivals(ready: true, upcoming: [_diwali]));
    expect(find.textContaining('Diwali is in 114 days'), findsOneWidget);
    expect(find.textContaining('INR 4,200 more'), findsOneWidget);
    expect(find.text('Coming up'), findsOneWidget);
  });

  testWidgets('with no history it shows the date and no invented cost', (tester) async {
    // The date is real; a number next to it would not be.
    await _pump(tester, const Festivals(ready: true, upcoming: [_bareDiwali]));
    expect(find.text('Diwali is in 114 days.'), findsOneWidget);
    expect(find.textContaining('more than'), findsNothing);
  });

  testWidgets('an out-of-date calendar renders nothing rather than a guess', (tester) async {
    // The baked dates ran out. Silence is the only honest option — a guessed
    // lunar date is worse than no festival feature at all.
    await _pump(tester, const Festivals(ready: false));
    expect(find.text('Coming up'), findsNothing);
  });

  testWidgets('nothing coming up means no card', (tester) async {
    await _pump(tester, const Festivals(ready: true, upcoming: []));
    expect(find.text('Coming up'), findsNothing);
  });

  testWidgets('the ones after next are listed briefly', (tester) async {
    await _pump(tester, const Festivals(ready: true, upcoming: [
      _bareDiwali,
      UpcomingFestival(name: 'Guru Nanak Jayanti', date: '2026-11-24', daysAway: 130, line: 'x'),
      UpcomingFestival(name: 'Christmas', date: '2026-12-25', daysAway: 161, line: 'y'),
    ]));
    expect(find.text('Then Guru Nanak Jayanti (130d) · Christmas (161d)'), findsOneWidget);
  });

  testWidgets('"Plan for it" hands the festival name to the flow', (tester) async {
    String? planned;
    await _pump(tester, const Festivals(ready: true, upcoming: [_diwali]),
        onPlan: (name) => planned = name);

    await tester.tap(find.text('Plan for Diwali'));
    await tester.pumpAndSettle();
    expect(planned, 'Diwali');
  });

  testWidgets('a moon-sighting hedge survives to the screen', (tester) async {
    await _pump(tester, const Festivals(ready: true, upcoming: [
      UpcomingFestival(
        name: 'Eid al-Fitr',
        date: '2027-03-09',
        daysAway: 7,
        approximate: true,
        line: 'Eid al-Fitr is in 7 days (the exact date depends on the moon sighting).',
      ),
    ]));
    expect(find.textContaining('depends on the moon sighting'), findsOneWidget);
  });
}
