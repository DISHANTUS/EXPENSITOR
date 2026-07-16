import 'package:expensitor_mobile/features/advisor/chat_models.dart';
import 'package:expensitor_mobile/features/advisor/widgets/follow_up_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// These cover the submit path itself, which earlier service-level tests never
/// touched — both bugs below were found by driving the real UI, not by tests.

FollowUpQuestion _freeTextQ() => const FollowUpQuestion(
      id: 'a1', kind: 'spending_shift', importance: 'medium',
      subjectLabel: 'Food & Dining',
      claim: 'Food & Dining has been running higher lately',
      question: 'Food & Dining has been running higher lately. What\'s changed?',
      responseType: 'free_text',
    );

FollowUpQuestion _choiceQ() => const FollowUpQuestion(
      id: 'b1', kind: 'forecast', importance: 'high',
      subjectLabel: 'Japan Fund', claim: 'reach Japan Fund by March',
      question: 'How is the Japan Fund going?',
      options: [
        FollowUpOption(label: 'Yes', value: 'yes'),
        FollowUpOption(label: 'No', value: 'no'),
      ],
    );

Widget _host(Widget child) => MaterialApp(home: Scaffold(body: SingleChildScrollView(child: child)));

void main() {
  testWidgets('free_text card sends the typed reason and clears it on success', (tester) async {
    String? sentValue;
    String? sentDetail;
    await tester.pumpWidget(_host(FollowUpCard(
      _freeTextQ(),
      onAnswer: (v, {detail}) async {
        sentValue = v;
        sentDetail = detail;
        return null; // success
      },
    )));

    await tester.enterText(find.byType(TextField), 'friend visiting, more takeout');
    await tester.tap(find.text('Send'));
    await tester.pumpAndSettle();

    expect(sentValue, 'explained');
    expect(sentDetail, 'friend visiting, more takeout');
    expect(find.text('friend visiting, more takeout'), findsNothing); // cleared
  });

  testWidgets('a failed send keeps the typed reason and shows the error', (tester) async {
    // Regression: onAnswer used to be fire-and-forget with an unconditional
    // clear(), so a network failure silently ate what the user wrote.
    await tester.pumpWidget(_host(FollowUpCard(
      _freeTextQ(),
      onAnswer: (v, {detail}) async => 'No connection. Check your network and try again.',
    )));

    await tester.enterText(find.byType(TextField), 'bike broke, taking the bus');
    await tester.tap(find.text('Send'));
    await tester.pumpAndSettle();

    expect(find.text('bike broke, taking the bus'), findsOneWidget); // NOT lost
    expect(find.text('No connection. Check your network and try again.'), findsOneWidget);
  });

  testWidgets('a too-thin reason shows the nudge inline and keeps the card open', (tester) async {
    // Regression: needs_more_detail produced no feedback at all in the compact
    // Home view — the card just sat there looking like nothing happened.
    await tester.pumpWidget(_host(FollowUpCard(
      _freeTextQ(),
      onAnswer: (v, {detail}) async => 'Could you say a little more about what changed?',
    )));

    await tester.enterText(find.byType(TextField), 'idk');
    await tester.tap(find.text('Send'));
    await tester.pumpAndSettle();

    expect(find.text('Could you say a little more about what changed?'), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget); // still answerable
    expect(find.text('idk'), findsOneWidget);       // their words are still there
  });

  testWidgets('an empty reason never fires a request', (tester) async {
    var calls = 0;
    await tester.pumpWidget(_host(FollowUpCard(
      _freeTextQ(),
      onAnswer: (v, {detail}) async {
        calls++;
        return null;
      },
    )));

    await tester.tap(find.text('Send'));
    await tester.pumpAndSettle();
    expect(calls, 0);
  });

  testWidgets('choice cards still answer with the chip value (no regression)', (tester) async {
    String? sentValue;
    await tester.pumpWidget(_host(FollowUpCard(
      _choiceQ(),
      onAnswer: (v, {detail}) async {
        sentValue = v;
        return null;
      },
    )));

    expect(find.byType(TextField), findsNothing); // choice != free_text
    await tester.tap(find.text('Yes'));
    await tester.pumpAndSettle();
    expect(sentValue, 'yes');
  });

  testWidgets('an answered card shows the acknowledgement instead of an input', (tester) async {
    await tester.pumpWidget(_host(FollowUpCard(
      _freeTextQ(),
      answered: 'Thanks for explaining — I’ll keep that in mind.',
      onAnswer: (v, {detail}) async => null,
    )));

    expect(find.text('Thanks for explaining — I’ll keep that in mind.'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
  });
}
