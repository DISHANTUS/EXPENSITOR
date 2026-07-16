import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../analytics/analytics.dart';
import '../facts/fact_sheet.dart';
import '../intervention/intervention_controller.dart';
import '../intervention/intervention_sheet.dart';
import '../theme/app_theme.dart';
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
    final top = ref.watch(topInterventionProvider);
    final orb = CompanionOrb(state: orbState, size: size);
    // When Advary has something to raise, the orb wears a pulsing attention ring
    // and a tap opens the talk sheet instead of a fun fact.
    return GestureDetector(
      // Opaque so the whole orb stays tappable even under the layered ring/badge.
      behavior: HitTestBehavior.opaque,
      onTap: top != null
          ? () {
              ref.read(analyticsProvider).track('intervention_opened', {'trigger': top.trigger.name});
              showInterventionSheet(context);
            }
          : () => showFactSheet(context),
      onDoubleTap: () => _showEncouragement(context),
      onLongPress: () => _showFeeling(context),
      child: top == null
          ? orb
          : _AttentionRing(
              size: size,
              color: top.ringColor(Theme.of(context).colorScheme),
              // "!" only when Advary is actually waiting on an answer; anything
              // that's merely news keeps the quieter dot.
              exclaim: top.wantsAnswer,
              child: orb,
            ),
    );
  }
}

/// A pulsing "I have something to say" halo around the orb — a steady breathing
/// glow + an expanding radar ping + a small badge. Subtle, never a popup.
class _AttentionRing extends StatefulWidget {
  const _AttentionRing({required this.size, required this.color, required this.child, this.exclaim = false});
  final double size;
  final Color color;
  final Widget child;

  /// Turns the badge dot into an exclamation mark: Advary is waiting on you.
  final bool exclaim;

  @override
  State<_AttentionRing> createState() => _AttentionRingState();
}

class _AttentionRingState extends State<_AttentionRing> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1500))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.size;
    return SizedBox(
      width: s,
      height: s,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.center,
        children: [
          // Expanding radar ping that fades as it grows.
          AnimatedBuilder(
            animation: _c,
            builder: (_, __) {
              final t = Curves.easeOut.transform(_c.value);
              return Container(
                width: s * (1 + 0.45 * t),
                height: s * (1 + 0.45 * t),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: widget.color.withValues(alpha: (1 - t) * 0.6), width: 2),
                ),
              );
            },
          ),
          // Steady breathing glow behind the orb.
          AnimatedBuilder(
            animation: _c,
            builder: (_, child) {
              final p = sin(_c.value * 2 * pi) * 0.5 + 0.5;
              return Container(
                width: s,
                height: s,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: widget.color.withValues(alpha: 0.25 + 0.35 * p),
                      blurRadius: 8 + 8 * p,
                      spreadRadius: 1,
                    ),
                  ],
                ),
                child: child,
              );
            },
            child: widget.child,
          ),
          // Badge, top-right: an exclamation mark when Advary is waiting on an
          // answer, otherwise a quiet dot.
          Positioned(
            top: -2,
            right: -2,
            child: Container(
              width: widget.exclaim ? 16 : 12,
              height: widget.exclaim ? 16 : 12,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: widget.color,
                border: Border.all(color: AppColors.hairline(0.85), width: 1.5),
              ),
              child: widget.exclaim
                  ? const Text(
                      '!',
                      // An explicit style, not a theme one: this renders inside
                      // overlay/scaffold layers where theme text styles resolve
                      // to nothing and the glyph silently disappears.
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        height: 1.05,
                        fontWeight: FontWeight.w900,
                      ),
                    )
                  : null,
            ),
          ),
        ],
      ),
    );
  }
}
