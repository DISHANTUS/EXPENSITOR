import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';

/// The journey rail (Sprint UI-X-2) — the shared visual language for Timeline and
/// Future Me: a glowing vertical path with luminous nodes and glass content cards.
/// One world, two directions (past behind, future ahead).

/// The aurora colour that suits a life event's kind.
Color colorForKind(String kind) => switch (kind) {
      'income' => AppColors.secondary,
      'lesson' => AppColors.secondary,
      'loan' || 'event' || 'life_event' => AppColors.accent,
      'achievement' || 'goal' || 'forecast' => AppColors.primary,
      _ => AppColors.primary,
    };

/// A glowing node on the rail. Milestones glow brighter and larger; future/dim
/// nodes are softer so the eye reads "ahead, not yet".
class GlowNode extends StatelessWidget {
  const GlowNode({
    super.key,
    required this.emoji,
    this.color = AppColors.primary,
    this.size = 38,
    this.highlight = false,
    this.dim = false,
  });

  final String emoji;
  final Color color;
  final double size;
  final bool highlight;
  final bool dim;

  @override
  Widget build(BuildContext context) {
    final glow = highlight ? 0.65 : (dim ? 0.16 : 0.40);
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(colors: [
          color.withValues(alpha: dim ? 0.22 : 0.55),
          color.withValues(alpha: dim ? 0.06 : 0.16),
        ]),
        border: Border.all(
            color: color.withValues(alpha: highlight ? 0.9 : (dim ? 0.25 : 0.4)),
            width: highlight ? 1.6 : 1),
        boxShadow: [
          BoxShadow(
              color: color.withValues(alpha: glow),
              blurRadius: highlight ? 22 : 12,
              spreadRadius: highlight ? 1 : 0),
        ],
      ),
      child: Text(emoji, style: TextStyle(fontSize: size * 0.46)),
    );
  }
}

/// The glowing segment of rail between two nodes. Stretches to the row height
/// (use inside an Expanded within an IntrinsicHeight Row).
class RailConnector extends StatelessWidget {
  const RailConnector({super.key, this.color = AppColors.primary, this.dim = false});
  final Color color;
  final bool dim;

  @override
  Widget build(BuildContext context) => Container(
        width: 2.5,
        margin: const EdgeInsets.symmetric(vertical: 2),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              color.withValues(alpha: dim ? 0.18 : 0.5),
              color.withValues(alpha: dim ? 0.04 : 0.14),
            ],
          ),
        ),
      );
}

/// One step on the journey: an optional leading label (e.g. a year), the rail
/// (node + connector), and a content card. The connector fills the row's height
/// so the rail stays continuous regardless of card size.
class JourneyRow extends StatelessWidget {
  const JourneyRow({
    super.key,
    required this.emoji,
    required this.child,
    this.leading,
    this.color = AppColors.primary,
    this.highlight = false,
    this.dim = false,
    this.last = false,
    this.nodeSize = 38,
  });

  final String emoji;
  final Widget child;
  final Widget? leading;
  final Color color;
  final bool highlight;
  final bool dim;
  final bool last;
  final double nodeSize;

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (leading != null)
            SizedBox(width: 42, child: Padding(padding: const EdgeInsets.only(top: 9), child: leading)),
          Column(
            children: [
              GlowNode(emoji: emoji, color: color, size: nodeSize, highlight: highlight, dim: dim),
              if (!last) Expanded(child: RailConnector(color: color, dim: dim)),
            ],
          ),
          const SizedBox(width: 12),
          Expanded(child: Padding(padding: const EdgeInsets.only(bottom: 14), child: child)),
        ],
      ),
    );
  }
}
