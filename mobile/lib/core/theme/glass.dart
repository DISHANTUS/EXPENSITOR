import 'dart:ui';

import 'package:flutter/material.dart';

/// Frosted-glass surface (Sprint UI-X). A blurred translucent panel with a hairline
/// border — the building block for cards, panels and chips over the aurora.
class GlassCard extends StatelessWidget {
  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.radius = 20,
    this.opacity = 0.06,
    this.blur = 18,
    this.gradient,
    this.borderColor,
    this.onTap,
    this.margin,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final double opacity;
  final double blur;
  final Gradient? gradient;       // optional tinted glass (e.g. relationship hero)
  final Color? borderColor;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry? margin;

  @override
  Widget build(BuildContext context) {
    final border = borderColor ?? Colors.white.withValues(alpha: 0.12);
    Widget panel = ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: gradient == null ? Colors.white.withValues(alpha: opacity) : null,
            gradient: gradient,
            borderRadius: BorderRadius.circular(radius),
            border: Border.all(color: border),
            boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.35), blurRadius: 24, offset: const Offset(0, 10))],
          ),
          child: child,
        ),
      ),
    );
    if (onTap != null) {
      panel = _Pressable(onTap: onTap!, child: panel);
    }
    return margin == null ? panel : Padding(padding: margin!, child: panel);
  }
}

/// A spring press-scale wrapper — every tappable surface feels alive (UI-X).
class _Pressable extends StatefulWidget {
  const _Pressable({required this.child, required this.onTap});
  final Widget child;
  final VoidCallback onTap;
  @override
  State<_Pressable> createState() => _PressableState();
}

class _PressableState extends State<_Pressable> {
  double _scale = 1;
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _scale = 0.97),
      onTapUp: (_) => setState(() => _scale = 1),
      onTapCancel: () => setState(() => _scale = 1),
      onTap: widget.onTap,
      child: AnimatedScale(
        scale: _scale,
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeOut,
        child: widget.child,
      ),
    );
  }
}

/// Gradient text (aurora) — for hero numbers/titles.
class GradientText extends StatelessWidget {
  const GradientText(this.text, {super.key, required this.style, this.gradient});
  final String text;
  final TextStyle style;
  final Gradient? gradient;
  @override
  Widget build(BuildContext context) {
    return ShaderMask(
      shaderCallback: (b) => (gradient ?? const LinearGradient(colors: [Color(0xFF7C5CFF), Color(0xFF00D4FF)]))
          .createShader(Rect.fromLTWH(0, 0, b.width, b.height)),
      child: Text(text, style: style.copyWith(color: Colors.white)),
    );
  }
}
