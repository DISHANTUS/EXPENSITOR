import 'package:expensitor_mobile/core/settings/settings_repository.dart';
import 'package:expensitor_mobile/core/widgets/otherable_chips.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('ReasonInterpretation parses and stores BOTH original + AI label', () {
    final r = ReasonInterpretation.fromJson({
      'original': 'Bought train tickets for my Japan JLPT trip',
      'label': 'JLPT',
      'tags': ['japan', 'jlpt', 'travel'],
      'confidence': 0.9,
      'needs_more': false,
    });
    expect(r.label, 'JLPT');
    expect(r.tags, contains('japan'));
    expect(r.needsMore, isFalse);
    final m = r.toMetadata();
    expect(m['why_original'], 'Bought train tickets for my Japan JLPT trip');
    expect(m['why_label'], 'JLPT');
    expect(m['tags'], contains('travel'));
  });

  testWidgets('OtherableChips: known chip reports value; Other reveals a text field', (tester) async {
    String? value;
    bool? isCustom;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: OtherableChips(
          options: const ['Salary', 'Freelance'],
          onChanged: (v, c) {
            value = v;
            isCustom = c;
          },
        ),
      ),
    ));

    await tester.tap(find.text('Salary'));
    await tester.pump();
    expect(value, 'Salary');
    expect(isCustom, isFalse);
    expect(find.byType(TextField), findsNothing);

    await tester.tap(find.textContaining('Other'));
    await tester.pump();
    expect(find.byType(TextField), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'Scholarship');
    await tester.pump();
    expect(value, 'Scholarship');
    expect(isCustom, isTrue);
  });
}
