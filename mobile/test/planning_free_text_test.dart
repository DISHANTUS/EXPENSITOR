import 'package:expensitor_mobile/core/theme/app_theme.dart';
import 'package:expensitor_mobile/features/budget_setup/planning_hub.dart';
import 'package:expensitor_mobile/features/advisor/advisor_chat_repository.dart';
import 'package:expensitor_mobile/features/advisor/chat_models.dart';
import 'package:expensitor_mobile/features/budget_setup/planning_repository.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Stands in for the backend's planning-intent layer, so these tests pin the
/// UI's half of the contract: given what Advary understood, does the flow open
/// in the right place with the right things pre-filled?
class _FakePlanning implements PlanningRepository {
  _FakePlanning(this.result, {this.error});
  final PlanningIntent result;
  final Object? error;
  String? lastText;

  @override
  Future<PlanningIntent> interpret(String text) async {
    lastText = text;
    if (error != null) throw error!;
    return result;
  }
}

Widget _hub(_FakePlanning fake, {Key? key}) => ProviderScope(
      overrides: [
        planningRepositoryProvider.overrideWithValue(fake),
        // No check-in questions here; that surface has its own test. Overriding
        // it also keeps the real fetch (and its timers) out of these tests.
        dueFollowUpsProvider.overrideWith((ref) async => const <FollowUpQuestion>[]),
      ],
      // The REAL theme: it makes buttons full-width, which is what broke the
      // flow's Next button on a device once already.
      child: MaterialApp(theme: AppTheme.dark(), home: Scaffold(body: PlanningHub(key: key))),
    );

Future<void> _say(WidgetTester tester, String text) async {
  await tester.enterText(find.widgetWithText(TextField, 'Tell me in your words'), text);
  await tester.pump();
  await tester.tap(find.byTooltip('Read this'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('the hub leads with free text and still offers the tiles', (tester) async {
    await tester.pumpWidget(_hub(_FakePlanning(const PlanningIntent(kind: 'other'))));
    await tester.pumpAndSettle();

    expect(find.text('What are you planning?'), findsOneWidget);
    expect(find.widgetWithText(TextField, 'Tell me in your words'), findsOneWidget);
    // Typing is never the ONLY way in.
    expect(find.text('Buy something'), findsOneWidget);
    expect(find.text('Save for a goal'), findsOneWidget);
  });

  testWidgets('a fully-specified sentence asks nothing but the confirm', (tester) async {
    final fake = _FakePlanning(PlanningIntent(
      kind: 'buy',
      item: 'headphones',
      amount: 3000,
      targetDate: DateTime(2026, 12, 31),
    ));
    await tester.pumpWidget(_hub(fake));
    await tester.pumpAndSettle();
    await _say(tester, 'buy headphones for 3000 by december');

    expect(fake.lastText, 'buy headphones for 3000 by december');
    // Straight to the last step — the item/cost questions are already answered.
    expect(find.text('When do you want it by?'), findsOneWidget);
    expect(find.text('Add to plan'), findsOneWidget);
    // And it shows its work, so a misread is visible rather than silent.
    expect(find.textContaining('headphones'), findsWidgets);
    expect(find.textContaining('INR 3000'), findsOneWidget);
  });

  testWidgets('a half-specified sentence resumes at the first thing we do not know', (tester) async {
    final fake = _FakePlanning(const PlanningIntent(
      kind: 'buy',
      item: 'headphone',
      missing: ['amount', 'target_date'],
    ));
    await tester.pumpWidget(_hub(fake));
    await tester.pumpAndSettle();
    await _say(tester, 'my headphone broke');

    // It knows the item, so it never re-asks for it — it asks the next thing,
    // naming what the user already said.
    expect(find.text('Roughly how much does headphone cost?'), findsOneWidget);
  });

  testWidgets('a pre-filled answer is editable, not baked in', (tester) async {
    await tester.pumpWidget(_hub(_FakePlanning(PlanningIntent(
      kind: 'buy',
      item: 'headphones',
      amount: 3000,
      targetDate: DateTime(2026, 12, 31),
    ))));
    await tester.pumpAndSettle();
    await _say(tester, 'buy headphones for 3000 by december');

    // Back walks into the earlier steps, which hold what we understood.
    await tester.tap(find.text('Back'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(TextField, '3000'), findsOneWidget); // "3000", never "3000.0"

    await tester.tap(find.text('Back'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(TextField, 'headphones'), findsOneWidget);
  });

  testWidgets('each kind opens its own flow', (tester) async {
    for (final (kind, prompt) in [
      ('save', 'How much do you want to save?'),
      ('subscription', 'How much is it per month?'),
    ]) {
      // A fresh key per iteration: without one, Flutter reuses the previous
      // PlanningHub's State and the second pass never returns to the chooser.
      await tester.pumpWidget(
        _hub(_FakePlanning(PlanningIntent(kind: kind, item: 'thing')), key: ValueKey(kind)),
      );
      await tester.pumpAndSettle();
      await _say(tester, 'whatever');
      expect(find.text(prompt), findsOneWidget, reason: 'kind "$kind" should route to its own flow');
    }
  });

  testWidgets('something we cannot place hands the words to the advisor, not a dead end', (tester) async {
    await tester.pumpWidget(_hub(_FakePlanning(const PlanningIntent(kind: 'other'))));
    await tester.pumpAndSettle();
    await _say(tester, 'my friend owes me 500');

    expect(find.text("Let's talk that through"), findsOneWidget);
    // The user's exact words are carried over — they never retype them.
    expect(find.text('"my friend owes me 500"'), findsOneWidget);
    expect(find.text('Talk to Advary'), findsOneWidget);
  });

  testWidgets('understanding is a convenience, never a gate', (tester) async {
    // With the backend unreachable the screen must still work: say so, and
    // leave the tiles right there. Understanding failing must never mean
    // planning failing.
    final fake = _FakePlanning(const PlanningIntent(kind: 'other'), error: Exception('offline'));
    await tester.pumpWidget(_hub(fake));
    await tester.pumpAndSettle();

    await tester.enterText(find.widgetWithText(TextField, 'Tell me in your words'), 'buy a bike');
    await tester.pump();
    await tester.tap(find.byTooltip('Read this'));
    await tester.pumpAndSettle();

    expect(find.text('Buy something'), findsOneWidget);
    await tester.tap(find.text('Buy something'));
    await tester.pumpAndSettle();
    expect(find.text('What are you planning to buy?'), findsOneWidget);
  });

  testWidgets('the seeded flow lays out with a usable Next under the real theme', (tester) async {
    await tester.pumpWidget(_hub(_FakePlanning(const PlanningIntent(kind: 'buy', item: 'headphone'))));
    await tester.pumpAndSettle();
    await _say(tester, 'my headphone broke');

    expect(tester.takeException(), isNull);
    final size = tester.getSize(find.widgetWithText(FilledButton, 'Next'));
    expect(size.width, greaterThan(0));
    expect(size.width, lessThan(double.infinity));
  });
}
