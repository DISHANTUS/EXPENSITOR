import 'package:expensitor_mobile/features/budget_setup/planning_hub.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('the Planning chooser offers all four intents', (tester) async {
    await tester.pumpWidget(const ProviderScope(
      child: MaterialApp(home: Scaffold(body: PlanningHub())),
    ));
    await tester.pump();

    expect(find.text('Buy something'), findsOneWidget);
    expect(find.text('Start a subscription'), findsOneWidget);
    expect(find.text('Save for a goal'), findsOneWidget);
    expect(find.text('Something else'), findsOneWidget);
  });

  testWidgets('picking "Buy something" opens the adaptive purchase flow', (tester) async {
    await tester.pumpWidget(const ProviderScope(
      child: MaterialApp(home: Scaffold(body: PlanningHub())),
    ));
    await tester.pump();

    await tester.tap(find.text('Buy something'));
    await tester.pumpAndSettle();

    // First adaptive question of the buy flow.
    expect(find.text('What are you planning to buy?'), findsOneWidget);
    expect(find.text('Next'), findsOneWidget);
    expect(find.text('Back'), findsOneWidget);
  });

  testWidgets('the purchase flow only advances once an item is named', (tester) async {
    await tester.pumpWidget(const ProviderScope(
      child: MaterialApp(home: Scaffold(body: PlanningHub())),
    ));
    await tester.pump();
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
}
