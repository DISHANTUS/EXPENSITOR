import 'package:expensitor_mobile/core/theme/app_theme.dart';
import 'package:expensitor_mobile/features/advisor/advisor_chat_repository.dart';
import 'package:expensitor_mobile/features/advisor/chat_models.dart';
import 'package:expensitor_mobile/features/budget_setup/planning_hub.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Advary's check-in questions render on this page, and the fetch behind them
/// leaves a pending timer in tests. Stub it: these tests are about the flows.
final _noQuestions = <Override>[
  dueFollowUpsProvider.overrideWith((ref) async => const <FollowUpQuestion>[]),
];

/// The REAL app theme — this matters. It sets filled buttons to
/// minimumSize: Size.fromHeight(50) (i.e. width: double.infinity). A bare
/// FilledButton inside a Row then gets an infinite tight width and fails
/// layout — invisible and untappable in release. A test on the default theme
/// can't reproduce that, which is exactly how it reached a device.
Widget _themedHub() => ProviderScope(
      overrides: _noQuestions,
      child: MaterialApp(theme: AppTheme.dark(), home: const Scaffold(body: PlanningHub())),
    );

Widget _plainHub() => ProviderScope(
      overrides: _noQuestions,
      child: const MaterialApp(home: Scaffold(body: PlanningHub())),
    );

Widget _hubWithQuestions(List<FollowUpQuestion> qs) => ProviderScope(
      overrides: [dueFollowUpsProvider.overrideWith((ref) async => qs)],
      child: MaterialApp(theme: AppTheme.dark(), home: const Scaffold(body: PlanningHub())),
    );

const _q = FollowUpQuestion(
  id: 'a1',
  kind: 'spending_shift',
  importance: 'high',
  claim: 'Food spending rose',
  question: 'Your food spending is up lately — what changed?',
  responseType: 'free_text',
);

void main() {
  testWidgets('the Planning chooser offers all four intents', (tester) async {
    await tester.pumpWidget(_plainHub());
    await tester.pumpAndSettle();

    expect(find.text('Buy something'), findsOneWidget);
    expect(find.text('Start a subscription'), findsOneWidget);
    expect(find.text('Save for a goal'), findsOneWidget);
    expect(find.text('Something else'), findsOneWidget);
  });

  testWidgets('the questions the orb points at are actually on this page', (tester) async {
    // The orb's "!" tells the user their questions are waiting on Planning and
    // offers a ride here. If they land and find nothing, the orb lied — so this
    // pins the destination to the promise.
    await tester.pumpWidget(_hubWithQuestions([_q]));
    await tester.pumpAndSettle();

    expect(find.text('A question for you'), findsOneWidget);
    expect(find.text('Your food spending is up lately — what changed?'), findsOneWidget);
    // ...and the rest of the page still works.
    expect(find.text('Buy something'), findsOneWidget);
  });

  testWidgets('with nothing to ask, the questions section stays out of the way', (tester) async {
    await tester.pumpWidget(_hubWithQuestions(const []));
    await tester.pumpAndSettle();

    expect(find.textContaining('question for you'), findsNothing);
    expect(find.text('What are you planning?'), findsOneWidget);
  });

  testWidgets('two questions are counted, not pluralised wrong', (tester) async {
    await tester.pumpWidget(_hubWithQuestions([_q, const FollowUpQuestion(
      id: 'a2',
      kind: 'spending_shift',
      importance: 'low',
      claim: 'c',
      question: 'And transport?',
      responseType: 'free_text',
    )]));
    await tester.pumpAndSettle();

    expect(find.text('2 questions for you'), findsOneWidget);
  });

  testWidgets('picking "Buy something" opens the adaptive purchase flow', (tester) async {
    await tester.pumpWidget(_plainHub());
    await tester.pumpAndSettle();

    await tester.tap(find.text('Buy something'));
    await tester.pumpAndSettle();

    // First adaptive question of the buy flow.
    expect(find.text('What are you planning to buy?'), findsOneWidget);
    expect(find.text('Next'), findsOneWidget);
    expect(find.text('Back'), findsOneWidget);
  });

  testWidgets('the purchase flow only advances once an item is named', (tester) async {
    await tester.pumpWidget(_plainHub());
    await tester.pumpAndSettle();
    await tester.tap(find.text('Buy something'));
    await tester.pumpAndSettle();

    // Next is disabled with an empty field...
    final nextBefore = tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Next'));
    expect(nextBefore.onPressed, isNull);

    await tester.enterText(find.byType(TextField), 'Headphones');
    await tester.pump();

    // ...and enabled once there's an answer.
    final nextAfter = tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Next'));
    expect(nextAfter.onPressed, isNotNull);
  });

  testWidgets('under the real theme, every flow lays out with a usable Next button', (tester) async {
    // Regression: caught on-device, not by tests. Under the real theme the
    // buy flow's Next button threw "BoxConstraints forces an infinite width"
    // and silently vanished (release swallows the assert), so the flow was a
    // dead end. Each flow's buttons must be Expanded inside their Row.
    await tester.pumpWidget(_themedHub());
    await tester.pumpAndSettle();
    await tester.tap(find.text('Buy something'));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull, reason: 'no layout assert under the real theme');
    final size = tester.getSize(find.widgetWithText(FilledButton, 'Next'));
    expect(size.width, greaterThan(0));
    expect(size.width, lessThan(double.infinity));
    expect(size.height, greaterThan(0));
  });

  testWidgets('the "something else" hand-off also lays out under the real theme', (tester) async {
    await tester.pumpWidget(_themedHub());
    await tester.pumpAndSettle();
    await tester.tap(find.text('Something else'));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    final size = tester.getSize(find.widgetWithText(FilledButton, 'Talk to Advary'));
    expect(size.width, greaterThan(0));
    expect(size.width, lessThan(double.infinity));
  });

  testWidgets('the subscription flow lays out under the real theme', (tester) async {
    await tester.pumpWidget(_themedHub());
    await tester.pumpAndSettle();
    await tester.tap(find.text('Start a subscription'));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.text('Which subscription?'), findsOneWidget);
    expect(tester.getSize(find.widgetWithText(FilledButton, 'Next')).width, greaterThan(0));
  });
}
