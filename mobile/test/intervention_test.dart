import 'package:expensitor_mobile/core/intervention/intervention.dart';
import 'package:expensitor_mobile/core/intervention/intervention_controller.dart';
import 'package:expensitor_mobile/core/intervention/intervention_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('InterventionController', () {
    test('add is idempotent by id; resolve removes it and records the fact', () {
      final c = InterventionController();
      const i = Intervention(id: 'a', trigger: InterventionTrigger.generic, title: 'T', message: 'M');
      c.add(i);
      c.add(i); // same id → ignored
      expect(c.state.manual.length, 1);

      c.resolve('a',
          fact: const Fact(type: 'transport_assistance', person: 'Kaguya', attributes: {'frequency': 'daily'}));
      expect(c.state.resolved.contains('a'), isTrue);
      expect(c.state.facts.length, 1);
      expect(c.state.facts.first.toJson(), {'type': 'transport_assistance', 'person': 'Kaguya', 'frequency': 'daily'});
    });

    test('add ignores an already-resolved id (no resurrection)', () {
      final c = InterventionController()..resolve('a');
      c.add(const Intervention(id: 'a', trigger: InterventionTrigger.generic, title: 'T', message: 'M'));
      expect(c.state.manual, isEmpty);
    });
  });

  test('pendingInterventionsProvider sorts by priority and drops resolved', () {
    final container = ProviderContainer(
      overrides: [
        reminderInterventionsProvider.overrideWith((ref) async => const []),
        payableInterventionsProvider.overrideWith((ref) async => const []),
      ],
    );
    addTearDown(container.dispose);
    container.listen(pendingInterventionsProvider, (_, __) {}); // keep alive

    final n = container.read(interventionControllerProvider.notifier);
    n.add(const Intervention(id: 'low', trigger: InterventionTrigger.reminder, title: 'L', message: '', priority: InterventionPriority.low));
    n.add(const Intervention(id: 'urgent', trigger: InterventionTrigger.borrowedMoney, title: 'U', message: '', priority: InterventionPriority.urgent));

    var pending = container.read(pendingInterventionsProvider);
    expect(pending.map((i) => i.id), ['urgent', 'low']); // highest priority first

    n.resolve('urgent');
    pending = container.read(pendingInterventionsProvider);
    expect(pending.map((i) => i.id), ['low']);
  });

  testWidgets('tap-to-talk sheet: opener → Let\'s talk → message + action', (tester) async {
    tester.view.devicePixelRatio = 1.0; // tall viewport so the bottom sheet fits on-screen
    tester.view.physicalSize = const Size(1080, 3200);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    late WidgetRef ref;
    await tester.pumpWidget(ProviderScope(
      overrides: [
        reminderInterventionsProvider.overrideWith((r) async => const []),
        payableInterventionsProvider.overrideWith((r) async => const []),
      ],
      child: MaterialApp(
        home: Consumer(builder: (context, r, _) {
          ref = r;
          return Scaffold(
            body: Builder(
              builder: (context) => Center(
                child: ElevatedButton(onPressed: () => showInterventionSheet(context), child: const Text('open')),
              ),
            ),
          );
        }),
      ),
    ));

    ref.read(interventionControllerProvider.notifier).add(const Intervention(
          id: 'r1',
          trigger: InterventionTrigger.reminder,
          title: "🎂 Kaguya's birthday — in 3 days",
          message: 'Her birthday is coming up. Want to get ready for it?',
          actionLabel: 'Open the day',
        ));
    await tester.pump();

    await tester.tap(find.text('open'));
    await tester.pump(const Duration(milliseconds: 600));
    // The orb → talk-sheet wiring works: tapping opens Advary's opener for the
    // top-priority intervention, with the two-choice gateway every trigger shares.
    expect(find.text('Advary wants to talk'), findsOneWidget);
    expect(find.text("Let's talk"), findsOneWidget);
    expect(find.text('Later'), findsOneWidget);
  });
}
