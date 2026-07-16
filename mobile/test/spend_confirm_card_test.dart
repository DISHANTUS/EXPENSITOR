import 'package:expensitor_mobile/features/home/predicted_expense_repository.dart';
import 'package:expensitor_mobile/features/home/widgets/spend_confirm_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _travel = PredictedExpense(
  categoryId: 'cat-1', label: 'Transportation', amount: 200, dayType: 'weekday', confidence: 'high',
);

// Top-level tear-offs so the card can be const-constructed in the layout test.
Future<String?> _noop(double _) async => null;
void _noopVoid() {}

Widget _host(Widget child) => MaterialApp(home: Scaffold(body: SingleChildScrollView(child: child)));

void main() {
  testWidgets('lays out cleanly in the real Home context (Column inside ListView)', (tester) async {
    // Regression: the button row used a Row+Spacer, which demands a bounded
    // width the card doesn't get inside a Column-in-ListView. It threw
    // "BoxConstraints forces an infinite width" and collapsed the whole card
    // to zero size — so `live=2` still rendered nothing on-device. The earlier
    // tests used a width-bounding host and missed it.
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: ListView(children: const [
          Column(children: [
            SpendConfirmCard(
              prediction: _travel, currency: 'INR',
              onConfirm: _noop, onDismiss: _noopVoid,
            ),
          ]),
        ]),
      ),
    ));

    expect(tester.takeException(), isNull);
    expect(find.text('Yes'), findsOneWidget);
    expect(find.text('Amount changed'), findsOneWidget);
    // The card must actually occupy space, not silently collapse.
    expect(tester.getSize(find.byType(SpendConfirmCard)).height, greaterThan(0));
  });

  testWidgets('asks about the usual amount in plain words', (tester) async {
    await tester.pumpWidget(_host(SpendConfirmCard(
      prediction: _travel, currency: 'INR',
      onConfirm: (_) async => null, onDismiss: () {},
    )));

    expect(find.text('Is the ₹200 for Transportation over?'), findsOneWidget);
    expect(find.text('Yes'), findsOneWidget);
    expect(find.text('No'), findsOneWidget);
  });

  testWidgets('Yes confirms the predicted amount unchanged', (tester) async {
    double? confirmed;
    await tester.pumpWidget(_host(SpendConfirmCard(
      prediction: _travel, currency: 'INR',
      onConfirm: (a) async {
        confirmed = a;
        return null;
      },
      onDismiss: () {},
    )));

    await tester.tap(find.text('Yes'));
    await tester.pumpAndSettle();
    expect(confirmed, 200);
  });

  testWidgets('No dismisses without ever writing an expense', (tester) async {
    var dismissed = false;
    var confirms = 0;
    await tester.pumpWidget(_host(SpendConfirmCard(
      prediction: _travel, currency: 'INR',
      onConfirm: (_) async {
        confirms++;
        return null;
      },
      onDismiss: () => dismissed = true,
    )));

    await tester.tap(find.text('No'));
    await tester.pumpAndSettle();
    expect(dismissed, isTrue);
    expect(confirms, 0);
  });

  testWidgets('"Amount changed" lets the user log a corrected number', (tester) async {
    double? confirmed;
    await tester.pumpWidget(_host(SpendConfirmCard(
      prediction: _travel, currency: 'INR',
      onConfirm: (a) async {
        confirmed = a;
        return null;
      },
      onDismiss: () {},
    )));

    await tester.tap(find.text('Amount changed'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '260');
    await tester.tap(find.text('Yes'));
    await tester.pumpAndSettle();

    expect(confirmed, 260, reason: 'the corrected amount, not the prediction');
  });

  testWidgets('a corrected amount is reflected back in the question text', (tester) async {
    await tester.pumpWidget(_host(SpendConfirmCard(
      prediction: _travel, currency: 'INR',
      onConfirm: (_) async => null, onDismiss: () {},
    )));

    await tester.tap(find.text('Amount changed'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '260');
    await tester.tap(find.text('Done'));
    await tester.pumpAndSettle();

    expect(find.text('Is the ₹260 for Transportation over?'), findsOneWidget);
  });

  testWidgets('a junk amount is refused instead of posting garbage', (tester) async {
    var confirms = 0;
    await tester.pumpWidget(_host(SpendConfirmCard(
      prediction: _travel, currency: 'INR',
      onConfirm: (_) async {
        confirms++;
        return null;
      },
      onDismiss: () {},
    )));

    await tester.tap(find.text('Amount changed'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '0');
    await tester.tap(find.text('Yes'));
    await tester.pumpAndSettle();

    expect(confirms, 0);
    expect(find.text('Enter an amount above zero.'), findsOneWidget);
  });

  testWidgets('a failed confirm surfaces the error and stays actionable', (tester) async {
    await tester.pumpWidget(_host(SpendConfirmCard(
      prediction: _travel, currency: 'INR',
      onConfirm: (_) async => 'No connection. Check your network and try again.',
      onDismiss: () {},
    )));

    await tester.tap(find.text('Yes'));
    await tester.pumpAndSettle();

    expect(find.text('No connection. Check your network and try again.'), findsOneWidget);
    expect(find.text('Yes'), findsOneWidget); // retryable
  });
}
