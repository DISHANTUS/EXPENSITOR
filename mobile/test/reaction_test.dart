// Sprint 5a.5 — companion reaction queue + copy table + DTO parsing.

import 'package:expensitor_mobile/core/companion/reaction.dart';
import 'package:expensitor_mobile/core/companion/reaction_queue.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('ReactionQueue', () {
    late ProviderContainer c;
    late ReactionQueue q;
    List<CompanionReaction> list() => c.read(reactionQueueProvider);

    setUp(() {
      c = ProviderContainer();
      q = c.read(reactionQueueProvider.notifier);
    });
    tearDown(() => c.dispose()); // cancels the prune/rotate timers

    test('push surfaces the reaction as current', () {
      q.push(reactionFor('income'));
      expect(list(), hasLength(1));
      expect(q.current?.kind, 'income');
    });

    test('dedupes by signature — same reaction never doubles up', () {
      q.push(reactionFor('income'));
      q.push(reactionFor('income'));
      expect(list(), hasLength(1));
    });

    test('higher importance wins the front regardless of push order', () {
      q.push(reactionFor('expense')); // normal
      q.push(reactionFor('loan_repaid')); // milestone
      expect(q.current?.kind, 'loan_repaid');
      expect(q.current?.importance, ReactionImportance.milestone);
    });

    test('achievement outranks a milestone', () {
      q.push(reactionFor('loan_repaid')); // milestone
      q.push(const CompanionReaction(
          kind: 'achievement', emoji: '🏆', headline: 'Achievement unlocked!',
          importance: ReactionImportance.achievement));
      expect(q.current?.importance, ReactionImportance.achievement);
    });

    test('dismiss removes the reaction and it does not resurface', () {
      final r = reactionFor('income');
      q.push(r);
      q.dismiss(r);
      expect(list(), isEmpty);
      q.push(r); // already seen → stays gone
      expect(list(), isEmpty);
    });
  });

  group('reactionFor copy table', () {
    test('income / expense / event / lent map to their emoji + kind', () {
      expect(reactionFor('income').emoji, '💼');
      expect(reactionFor('expense').emoji, '🧾');
      expect(reactionFor('event').emoji, '📅');
      expect(reactionFor('lent').emoji, '💸');
    });

    test('loan_repaid is a milestone', () {
      expect(reactionFor('loan_repaid').importance, ReactionImportance.milestone);
    });

    test('goal interpolates the label', () {
      expect(reactionFor('goal', label: 'Japan Fund').detail, contains('Japan Fund'));
    });

    test('unknown kind degrades to a thought bubble', () {
      final r = reactionFor('mystery');
      expect(r.emoji, '💭');
    });
  });

  group('CompanionReaction.fromJson (backend pending_reactions)', () {
    test('parses an achievement with timeline label + tap route', () {
      final r = CompanionReaction.fromJson(const {
        'kind': 'achievement', 'emoji': '🏆', 'headline': 'Achievement unlocked!',
        'detail': 'Completed your Japan Fund goal', 'importance': 'achievement',
        'timeline_label': 'Completed your Japan Fund goal', 'signature': 'ach:goal_completed:2026-06-17',
      });
      expect(r.importance, ReactionImportance.achievement);
      expect(r.timelineLabel, contains('Japan Fund'));
      expect(r.ttl, const Duration(minutes: 3));
      expect(r.signature, 'ach:goal_completed:2026-06-17');
    });

    test('overspend carries its tap route', () {
      final r = CompanionReaction.fromJson(const {
        'kind': 'overspend', 'emoji': '⚠️', 'headline': 'You’re over today’s budget.',
        'importance': 'normal', 'tap_route': '/plan-today', 'signature': 'overspend:2026-06-17',
      });
      expect(r.tapRoute, '/plan-today');
      expect(r.ttl, const Duration(seconds: 40));
    });
  });
}
