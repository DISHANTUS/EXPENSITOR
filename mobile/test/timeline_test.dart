// Sprint 6a — Life Timeline DTO parsing (mirrors the backend /timeline shape).

import 'package:expensitor_mobile/core/timeline/timeline_models.dart';
import 'package:flutter_test/flutter_test.dart';

const _json = {
  'chapters': [
    {
      'label': '2026',
      'entries': [
        {'date': '2026-01-05', 'title': 'Recorded your first income', 'detail': '', 'kind': 'achievement',
         'importance': 'life_milestone', 'when': 'past', 'icon': '💼'},
        {'date': '2026-07-17', 'title': 'Ravi to repay ₹3,000', 'detail': '', 'kind': 'loan',
         'importance': 'medium', 'when': 'future', 'icon': '💸'},
      ],
    },
    {
      'label': '2027',
      'entries': [
        {'date': '2027-07-01', 'title': 'Reach your Japan Fund goal', 'detail': 'Target ₹300,000',
         'kind': 'goal', 'importance': 'high', 'when': 'future', 'icon': '🎯'},
      ],
    },
  ],
  'past_count': 1,
  'present_count': 0,
  'future_count': 2,
  'headline': 'Here’s your story so far — 1 chapter behind you, 2 ahead.',
};

void main() {
  test('parses chapters, entries, counts and headline', () {
    final tl = Timeline.fromJson(Map<String, dynamic>.from(_json));
    expect(tl.isEmpty, isFalse);
    expect(tl.chapters.map((c) => c.label).toList(), ['2026', '2027']);
    expect(tl.futureCount, 2);
    expect(tl.headline, contains('story so far'));

    final first = tl.chapters.first.entries.first;
    expect(first.title, 'Recorded your first income');
    expect(first.isMilestone, isTrue);
    expect(first.isFuture, isFalse);

    final japan = tl.chapters[1].entries.first;
    expect(japan.isFuture, isTrue);
    expect(japan.detail, 'Target ₹300,000');
    expect(japan.icon, '🎯');
  });

  test('empty timeline parses cleanly', () {
    final tl = Timeline.fromJson(const {'chapters': [], 'headline': 'Your story starts here.'});
    expect(tl.isEmpty, isTrue);
    expect(tl.headline, 'Your story starts here.');
  });
}
