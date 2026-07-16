import 'package:expensitor_mobile/core/companion/companion_orb.dart';
import 'package:expensitor_mobile/core/companion/companion_orb_button.dart';
import 'package:expensitor_mobile/core/intervention/intervention.dart';
import 'package:expensitor_mobile/core/intervention/intervention_controller.dart';
import 'package:expensitor_mobile/core/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// The derived providers each hit the network; stubbed to empty so a test is
/// about the orb, not about dio.
final _quiet = <Override>[
  payableInterventionsProvider.overrideWith((ref) async => const <Intervention>[]),
  reminderInterventionsProvider.overrideWith((ref) async => const <Intervention>[]),
  relationshipInterventionsProvider.overrideWith((ref) async => const <Intervention>[]),
  questionInterventionsProvider.overrideWith((ref) async => const <Intervention>[]),
];

Future<ProviderContainer> _pumpOrb(WidgetTester tester) async {
  final container = ProviderContainer(overrides: _quiet);
  addTearDown(container.dispose);
  await tester.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: MaterialApp(
      theme: AppTheme.dark(),
      home: const Scaffold(body: Center(child: CompanionOrbButton(orbState: OrbState.idle))),
    ),
  ));
  // pump, never pumpAndSettle: the orb breathes and blinks on a repeating
  // controller, so there is no "settled" frame to wait for — it would hang.
  await tester.pump();
  return container;
}

Intervention _question() => const Intervention(
      id: 'questions:a|b',
      trigger: InterventionTrigger.pendingQuestions,
      title: '❓ I have 2 questions for you',
      message: 'They are waiting on the Planning page.',
      actionLabel: 'Take me there',
      actionRoute: '/budget-setup',
    );

void main() {
  group('the orb badge', () {
    testWidgets('is quiet when Advary has nothing to raise', (tester) async {
      await _pumpOrb(tester);
      expect(find.text('!'), findsNothing);
    });

    testWidgets('shows "!" when Advary is waiting on an answer', (tester) async {
      final container = await _pumpOrb(tester);
      container.read(interventionControllerProvider.notifier).add(_question());
      await tester.pump();

      expect(find.text('!'), findsOneWidget);
    });

    testWidgets('stays a quiet dot for news that needs no answer', (tester) async {
      // An exclamation has to MEAN something. If everything Advary notices gets
      // one, it degrades into decoration and stops being a signal.
      final container = await _pumpOrb(tester);
      container.read(interventionControllerProvider.notifier).add(const Intervention(
            id: 'reminder:1',
            trigger: InterventionTrigger.reminder,
            title: '📅 Something is coming up',
            message: 'Just so you know.',
            actionLabel: 'Open the day',
            actionRoute: '/date/2026-07-16',
          ));
      await tester.pump();

      expect(find.text('!'), findsNothing);
    });

    testWidgets('clears once the questions are answered', (tester) async {
      final container = await _pumpOrb(tester);
      final q = _question();
      container.read(interventionControllerProvider.notifier).add(q);
      await tester.pump();
      expect(find.text('!'), findsOneWidget);

      container.read(interventionControllerProvider.notifier).resolve(q.id);
      await tester.pump();
      expect(find.text('!'), findsNothing);
    });
  });

  group('wantsAnswer', () {
    test('is true whenever Advary needs something back from the user', () {
      expect(_question().wantsAnswer, isTrue);
      expect(
        const Intervention(
          id: 'x',
          trigger: InterventionTrigger.generic,
          title: 't',
          message: 'm',
          question: 'Did something change?',
          choices: [InterventionChoice('Yes')],
        ).wantsAnswer,
        isTrue,
      );
      expect(
        const Intervention(
          id: 'y',
          trigger: InterventionTrigger.relationshipLearning,
          title: 't',
          message: 'm',
          inputLabel: 'Their name',
        ).wantsAnswer,
        isTrue,
      );
    });

    test('is false for a message that only informs', () {
      expect(
        const Intervention(
          id: 'z',
          trigger: InterventionTrigger.reminder,
          title: 't',
          message: 'm',
          actionLabel: 'Open',
        ).wantsAnswer,
        isFalse,
      );
    });
  });
}
