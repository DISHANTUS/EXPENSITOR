import 'package:expensitor_mobile/core/companion/mood_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('MoodState parses primary/base/rotation/reasons/presence', () {
    final m = MoodState.fromJson({
      'primary': {'id': 'goal_completed', 'emoji': '🏆', 'label': 'Goal completed!', 'kind': 'override', 'priority': 3},
      'base': {'id': 'concerned', 'emoji': '😟', 'label': 'Concerned', 'kind': 'base', 'priority': 1},
      'rotation': [
        {'id': 'goal_completed', 'emoji': '🏆', 'label': 'Goal completed!', 'kind': 'override', 'priority': 3},
        {'id': 'concerned', 'emoji': '😟', 'label': 'Concerned', 'kind': 'base', 'priority': 1},
        {'id': 'salary', 'emoji': '💰', 'label': 'Salary arrived', 'kind': 'event', 'priority': 0},
      ],
      'reasons': [{'label': 'Budget exceeded', 'value': '25%'}, {'label': 'Red days', 'value': '4'}],
      'mood_word': 'Goal completed!',
      'presence_score': 65,
      'presence_band': 'familiar',
    });
    expect(m.primary.emoji, '🏆');
    expect(m.base.id, 'concerned');
    expect(m.rotation.length, 3);
    expect(m.rotation.map((f) => f.emoji), contains('💰'));
    expect(m.reasons.first.label, 'Budget exceeded');
    expect(m.presenceBand, 'familiar');
  });

  test('MoodState parses an embedded greeting (salutation + lines + special day)', () {
    final m = MoodState.fromJson({
      'primary': {'id': 'goal_completed', 'emoji': '🏆', 'label': 'Goal completed!'},
      'base': {'id': 'on_budget', 'emoji': '😊', 'label': 'Content'},
      'rotation': [{'id': 'goal_completed', 'emoji': '🏆', 'label': 'Goal completed!'}],
      'mood_word': 'Goal completed!',
      'presence_score': 70,
      'presence_band': 'familiar',
      'greeting': {
        'salutation': 'Good afternoon.',
        'lines': ['You completed your goal! 🏆', 'Have a good one.'],
        'category': 'special_day', 'summary': 'special_day:goal_completed',
        'special_day': 'goal_completed', 'tone': 'encouraging', 'narration_source': 'deterministic',
      },
    });
    expect(m.greeting!.salutation, 'Good afternoon.');
    expect(m.greeting!.lines.length, 2);
    expect(m.greeting!.specialDay, 'goal_completed');
    expect(m.greeting!.category, 'special_day');
  });

  test('Greeting parses narration fields (display/spoken/source)', () {
    final m = MoodState.fromJson({
      'primary': {'id': 'on_budget', 'emoji': '😊', 'label': 'Content'},
      'base': {'id': 'on_budget', 'emoji': '😊', 'label': 'Content'},
      'rotation': [{'id': 'on_budget', 'emoji': '😊', 'label': 'Content'}],
      'mood_word': 'Content', 'presence_score': 40, 'presence_band': 'learning',
      'greeting': {
        'salutation': 'Good afternoon.', 'lines': ['Your salary arrives today.'],
        'category': 'financial', 'summary': 'financial:salary', 'tone': 'encouraging',
        'display_text': 'Afternoon — salary lands today, by the way.',
        'spoken_text': 'Good afternoon. Your salary arrives today.',
        'narration_source': 'ollama',
      },
    });
    expect(m.greeting!.narrationSource, 'ollama');
    expect(m.greeting!.displayText, contains('salary'));
    expect(m.greeting!.spokenText, isNot(contains('—')));
  });

  test('Greeting parses reasons + pending_narration (polish)', () {
    final m = MoodState.fromJson({
      'primary': {'id': 'on_budget', 'emoji': '😊', 'label': 'Content'},
      'base': {'id': 'on_budget', 'emoji': '😊', 'label': 'Content'},
      'rotation': [{'id': 'on_budget', 'emoji': '😊', 'label': 'Content'}],
      'mood_word': 'Content', 'presence_score': 60, 'presence_band': 'familiar',
      'greeting': {
        'salutation': 'Good afternoon.',
        'lines': ['Ravi is expected to return ₹3,000 today 💸', "You're on a 12-day budget streak 🔥"],
        'category': 'relationship', 'summary': 'relationship:Ravi: ₹3,000', 'tone': 'encouraging',
        'reasons': [
          {'label': 'Repayment due today', 'detail': 'Ravi: ₹3,000'},
          {'label': 'Budget streak', 'detail': '12 days'},
        ],
        'display_text': 'Good afternoon. Ravi returns ₹3,000 today…',
        'spoken_text': 'Good afternoon. Ravi is expected to return 3,000 today.',
        'narration_source': 'deterministic', 'pending_narration': true,
      },
    });
    final g = m.greeting!;
    expect(g.lines.length, 2);
    expect(g.reasons.map((r) => r.label), contains('Repayment due today'));
    expect(g.reasons.first.detail, contains('Ravi'));
    expect(g.pendingNarration, isTrue);
  });

  test('MoodState tolerates a minimal payload (neutral)', () {
    final m = MoodState.fromJson({
      'primary': {'id': 'neutral', 'emoji': '🙂', 'label': 'Steady'},
      'base': {'id': 'neutral', 'emoji': '🙂', 'label': 'Steady'},
      'rotation': [{'id': 'neutral', 'emoji': '🙂', 'label': 'Steady'}],
      'mood_word': 'Steady',
      'presence_score': 0,
      'presence_band': 'new',
    });
    expect(m.rotation.single.emoji, '🙂');
    expect(m.reasons, isEmpty);
  });
}
