// Companion reactions (Sprint 5a.5) — temporary acknowledgements the companion
// shows right after the user does something (or the intelligence layer notices
// something). Shown over the greeting/commentary on ANY page; auto-expire.

import '../voice/voice_plan.dart';

enum ReactionImportance { normal, milestone, achievement }

class CompanionReaction {
  const CompanionReaction({
    required this.kind,
    required this.emoji,
    required this.headline,
    this.detail = '',
    this.importance = ReactionImportance.normal,
    this.tapRoute,
    this.timelineLabel,
    String? signature,
  }) : signature = signature ?? '$kind|$headline|$detail';

  final String kind;
  final String emoji;
  final String headline;
  final String detail;
  final ReactionImportance importance;
  final String? tapRoute;        // tapping the reaction navigates here (e.g. overspend → plan-today)
  final String? timelineLabel;   // achievements → a TimelineCandidate (Sprint 6)
  final String signature;        // dedup key

  factory CompanionReaction.fromJson(Map<String, dynamic> j) {
    final imp = (j['importance'] ?? 'normal').toString();
    return CompanionReaction(
      kind: (j['kind'] ?? 'thought').toString(),
      emoji: (j['emoji'] ?? '💭').toString(),
      headline: (j['headline'] ?? '').toString(),
      detail: (j['detail'] ?? '').toString(),
      importance: ReactionImportance.values.firstWhere((e) => e.name == imp, orElse: () => ReactionImportance.normal),
      tapRoute: j['tap_route']?.toString(),
      timelineLabel: j['timeline_label']?.toString(),
      signature: j['signature']?.toString(),
    );
  }

  /// How long the reaction stays before fading back to the normal greeting.
  Duration get ttl => switch (importance) {
        ReactionImportance.achievement => const Duration(minutes: 3),
        ReactionImportance.milestone => const Duration(minutes: 2),
        ReactionImportance.normal => const Duration(seconds: 40),
      };

  /// How the companion SPEAKS this reaction (Sprint 5b). Milestones/achievements
  /// get the celebration voice + a lead and may auto-play; normal acks stay
  /// neutral and tap-to-hear (never auto-played).
  VoicePlan get voicePlan {
    final celebrating = importance != ReactionImportance.normal;
    final lead = switch (kind) {
      'loan_repaid' => 'Good news!',
      'goal' || 'goal_completed' => 'Congratulations!',
      _ => importance == ReactionImportance.achievement ? 'Congratulations!' : null,
    };
    return VoicePlan(
      profile: celebrating ? 'celebration' : 'neutral',
      intensity: importance == ReactionImportance.achievement
          ? 'high'
          : (celebrating ? 'medium' : 'low'),
      lead: celebrating ? lead : null,
      deterministicSegments: [headline, if (detail.isNotEmpty) detail],
      signature: 'rx:$signature',
      autoPlay: celebrating,
    );
  }
}

/// The copy table for client-emitted action acknowledgements.
CompanionReaction reactionFor(String kind, {String? amount, String? label}) {
  switch (kind) {
    case 'income':
      return const CompanionReaction(kind: 'income', emoji: '💼',
          headline: 'Nice, I’ve recorded your income', detail: 'Your available budget’s updated.');
    case 'expense':
      return const CompanionReaction(kind: 'expense', emoji: '🧾',
          headline: 'Expense recorded', detail: 'I’ve updated today’s spending.');
    case 'event':
      return const CompanionReaction(kind: 'event', emoji: '📅',
          headline: 'Got it', detail: 'I’ve added that to your calendar.');
    case 'lent':
      return const CompanionReaction(kind: 'lent', emoji: '💸',
          headline: 'I’ve recorded that loan', detail: 'I’ll help you keep track of it.');
    case 'loan_repaid':
      return const CompanionReaction(kind: 'loan_repaid', emoji: '🎉', importance: ReactionImportance.milestone,
          headline: 'Good news', detail: 'That repayment has been marked as received.');
    case 'subscription':
      return const CompanionReaction(kind: 'subscription', emoji: '💳',
          headline: 'Subscription saved', detail: 'I’ll remind you before it renews.');
    case 'goal':
      return CompanionReaction(kind: 'goal', emoji: '🎯',
          headline: 'Great job', detail: 'You’re one step closer to your ${label ?? 'goal'}.');
    default:
      return CompanionReaction(kind: kind, emoji: '💭', headline: label ?? 'Noted', detail: '');
  }
}
