import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'reaction.dart';

int _rank(ReactionImportance i) => switch (i) {
      ReactionImportance.achievement => 2,
      ReactionImportance.milestone => 1,
      ReactionImportance.normal => 0,
    };

/// Holds the active reactions: highest-importance first, newest within a tier.
/// Each expires on its own TTL; multiple normals rotate so none are lost.
class ReactionQueue extends StateNotifier<List<CompanionReaction>> {
  ReactionQueue() : super(const []) {
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) => _prune());
    _rotator = Timer.periodic(const Duration(seconds: 4), (_) => _rotate());
  }

  late final Timer _ticker;
  late final Timer _rotator;
  final Map<String, DateTime> _expiry = {};
  final Set<String> _seen = {};

  CompanionReaction? get current => state.isEmpty ? null : state.first;

  void push(CompanionReaction r) {
    if (_seen.contains(r.signature)) return;     // don't repeat the same reaction
    _seen.add(r.signature);
    _expiry[r.signature] = DateTime.now().add(r.ttl);
    final next = [...state.where((x) => x.signature != r.signature), r];
    next.sort((a, b) => _rank(b.importance).compareTo(_rank(a.importance)));
    state = next;
  }

  void dismiss(CompanionReaction r) {
    _expiry.remove(r.signature);
    state = state.where((x) => x.signature != r.signature).toList();
  }

  void _prune() {
    final now = DateTime.now();
    final live = state.where((r) => (_expiry[r.signature] ?? now).isAfter(now)).toList();
    if (live.length != state.length) state = live;
  }

  void _rotate() {
    // Only cycle when everything showing is normal — milestones/achievements stay put.
    if (state.length > 1 && state.every((r) => r.importance == ReactionImportance.normal)) {
      state = [...state.skip(1), state.first];
    }
  }

  @override
  void dispose() {
    _ticker.cancel();
    _rotator.cancel();
    super.dispose();
  }
}

final reactionQueueProvider =
    StateNotifierProvider<ReactionQueue, List<CompanionReaction>>((_) => ReactionQueue());
