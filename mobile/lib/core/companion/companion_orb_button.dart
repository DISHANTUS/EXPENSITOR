import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../facts/fact_sheet.dart';
import 'companion_orb.dart';
import 'mood_models.dart';

/// The interactive companion orb. It feels alive rather than like a button:
///   • single tap  → a fun "Did you know?" fact (fallback content, on demand),
///   • double tap   → a word of encouragement (your real progress, or a warm nudge),
///   • long press   → "how I'm feeling" — the orb's mood + why.
class CompanionOrbButton extends ConsumerWidget {
  const CompanionOrbButton({
    super.key,
    required this.orbState,
    this.size = 48,
    this.live,
    this.encouragements = const [],
  });

  final OrbState orbState;
  final double size;
  /// Live mood (Home) — powers the long-press "how I'm feeling".
  final MoodState? live;
  /// User-specific lines to celebrate on double-tap (Home's thought). Falls back
  /// to a warm generic line elsewhere.
  final List<String> encouragements;

  static const _warm = [
    "You showed up today — that's the habit that builds everything.",
    "Small, steady steps are how every goal gets reached.",
    "Future you is grateful for the choices you're making now.",
    "Consistency beats intensity. You're doing the quiet work.",
    "Every logged expense is a little more clarity. Nice going.",
  ];

  void _showEncouragement(BuildContext context) {
    final lines = encouragements.where((l) => l.trim().isNotEmpty).toList();
    final body = lines.isNotEmpty ? lines : [_warm[Random().nextInt(_warm.length)]];
    final tt = Theme.of(context).textTheme;
    showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('A little encouragement'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [for (final l in body) Padding(padding: const EdgeInsets.only(bottom: 4), child: Text(l, style: tt.bodyMedium))],
        ),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Thanks'))],
      ),
    );
  }

  void _showFeeling(BuildContext context) {
    final m = live;
    showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text((m?.moodWord ?? '').isEmpty ? "How I'm feeling" : m!.moodWord),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: (m == null || m.reasons.isEmpty)
              ? [const Text("I'm steady — nothing's pulling my mood right now.")]
              : [for (final r in m.reasons) Text('• ${r.label}: ${r.value}')],
        ),
        actions: [TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('OK'))],
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return GestureDetector(
      onTap: () => showFactSheet(context),
      onDoubleTap: () => _showEncouragement(context),
      onLongPress: () => _showFeeling(context),
      child: CompanionOrb(state: orbState, size: size),
    );
  }
}
