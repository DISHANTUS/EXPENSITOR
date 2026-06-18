// Sprint 7 — client DTO parsing for memory surfaces (timeline search, relationships).

import 'package:expensitor_mobile/core/relationships/relationship_models.dart';
import 'package:expensitor_mobile/core/timeline/timeline_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('timeline entry carries person + chapter carries subtitle', () {
    final c = TimelineChapter.fromJson(const {
      'label': 'Japan Preparation', 'subtitle': 'Saving and planning for Japan',
      'entries': [
        {'title': 'Lent ₹3,000 to Ravi', 'date': '2026-06-02', 'kind': 'loan', 'importance': 'medium',
         'when': 'past', 'icon': '💸', 'person': 'Ravi'},
      ],
    });
    expect(c.subtitle, contains('Japan'));
    expect(c.entries.single.person, 'Ravi');
  });

  test('timeline search result parses summary + entries', () {
    final r = TimelineSearchResult.fromJson(const {
      'summary': '2 things involving Ravi',
      'entries': [
        {'title': 'Lent ₹3,000 to Ravi', 'kind': 'loan', 'importance': 'medium', 'when': 'past', 'person': 'Ravi'},
        {'title': 'Ravi repaid what they owed', 'kind': 'achievement', 'importance': 'medium', 'when': 'past'},
      ],
    });
    expect(r.summary, contains('Ravi'));
    expect(r.entries, hasLength(2));
  });

  test('relationship detail parses trust + memories + timeline', () {
    final d = RelationshipDetail.fromJson(const {
      'name': 'Ravi', 'relationship_type': 'friend', 'trust_note': 'Reliable so far',
      'companion_note': '2 recorded memories together.',
      'timeline': [
        {'title': 'Lent ₹3,000 to Ravi', 'kind': 'loan', 'importance': 'medium', 'when': 'past', 'person': 'Ravi'},
      ],
      'future': [],
      'memories': ['First memory: Lent ₹3,000 to Ravi'],
      'trust': {'label': 'Reliable', 'repaid': 1, 'total': 1, 'outstanding': null},
    });
    expect(d.name, 'Ravi');
    expect(d.trust!.label, 'Reliable');
    expect(d.trust!.repaid, 1);
    expect(d.memories.single, contains('First memory'));
    expect(d.timeline.single.person, 'Ravi');
  });
}
