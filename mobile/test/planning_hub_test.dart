import 'package:expensitor_mobile/core/theme/app_theme.dart';
import 'package:expensitor_mobile/features/budget_setup/planning_hub.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// The REAL app theme — this matters. It sets filled buttons to
/// minimumSize: Size.fromHeight(50) (i.e. width: double.infinity). A bare
/// FilledButton inside a Row then gets an infinite tight width and fails
/// layout — invisible and untappable in release. A test on the default theme
/// can't reproduce that, which is exactly how it reached a device.
Widget _themedHub() => ProviderScope(
      child: MaterialApp(theme: AppTheme.dark(), home: const Scaffold(body: PlanningHub())),
    );

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

  testWidgets('under the real theme, every flow lays out with a usable Next button', (tester) async {
    // Regression: caught on-device, not by tests. Under the real theme the
    // buy flow's Next button threw "BoxConstraints forces an infinite width"
    // and silently vanished (release swallows the assert), so the flow was a
    // dead end. Each flow's buttons must be Expanded inside their Row.
    await tester.pumpWidget(_themedHub());
    await tester.pump();
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
    await tester.pump();
    await tester.tap(find.text('Something else'));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    final size = tester.getSize(find.widgetWithText(FilledButton, 'Talk to Advary'));
    expect(size.width, greaterThan(0));
    expect(size.width, lessThan(double.infinity));
  });

  testWidgets('the subscription flow lays out under the real theme', (tester) async {
    await tester.pumpWidget(_themedHub());
    await tester.pump();
    await tester.tap(find.text('Start a subscription'));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.text('Which subscription?'), findsOneWidget);
    expect(tester.getSize(find.widgetWithText(FilledButton, 'Next')).width, greaterThan(0));
  });
}
