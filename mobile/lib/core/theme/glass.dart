import 'dart:ui';

import 'package:flutter/material.dart';

import 'app_theme.dart';

/// The app's one shared card surface (Sprint UI-X, extended for the 15-pack
/// "feels alive" rollout). Renders differently per [AppColors.active.surfaceStyle]
/// — frosted glass is one option among five now, not the only one — so every
/// existing call site re-skins correctly for free when the theme changes.
///
/// Contract for callers: [gradient]/[borderColor], when passed, are used as the
/// fill/border under EVERY surface style. [blur]/[opacity] only affect
/// [SurfaceStyle.glass] and are ignored otherwise (non-glass styles skip the
/// blur pass entirely — a free perf win).
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
    this.palette,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final double opacity;
  final double blur;
  final Gradient? gradient;       // optional tinted fill (e.g. relationship hero)
  final Color? borderColor;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry? margin;
  /// Override the palette (used by the theme picker to preview each pack's
  /// real card, not a hand-rolled mock); defaults to the active theme —
  /// mirrors [CompanionOrb]'s existing `palette` override.
  final AppPalette? palette;

  AppPalette get _p => palette ?? AppColors.active;
  Color _hairline(double alpha) =>
      (_p.brightness == Brightness.dark ? Colors.white : Colors.black).withValues(alpha: alpha);

  @override
  Widget build(BuildContext context) {
    Widget panel = switch (_p.surfaceStyle) {
      SurfaceStyle.glass => _glass(),
      SurfaceStyle.flatOutlined => _flat(),
      SurfaceStyle.neomorphic => _neomorphic(),
      SurfaceStyle.paperRuled => _flat(ruled: true),
      SurfaceStyle.panelBorder => _panelBorder(),
    };
    if (onTap != null) {
      panel = _Pressable(onTap: onTap!, child: panel);
    }
    return margin == null ? panel : Padding(padding: margin!, child: panel);
  }

  Widget _glass() {
    final border = borderColor ?? _hairline(0.12);
    return ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: gradient == null ? _hairline(opacity) : null,
            gradient: gradient,
            borderRadius: BorderRadius.circular(radius),
            border: Border.all(color: border),
            boxShadow: [BoxShadow(color: AppColors.scrim(0.35), blurRadius: 24, offset: const Offset(0, 10))],
          ),
          child: child,
        ),
      ),
    );
  }

  Widget _flat({bool ruled = false}) {
    final p = _p;
    final border = borderColor ?? p.on.withValues(alpha: 0.16);
    Widget content = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: gradient == null ? p.surface : null,
        gradient: gradient,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: border),
        boxShadow: [BoxShadow(color: AppColors.scrim(0.12), blurRadius: 14, offset: const Offset(0, 6))],
      ),
      child: child,
    );
    if (ruled) {
      content = ClipRRect(
        borderRadius: BorderRadius.circular(radius),
        child: Stack(children: [
          Positioned.fill(child: CustomPaint(painter: _RuledLinesPainter(p.on.withValues(alpha: 0.08)))),
          content,
        ]),
      );
    }
    return content;
  }

  Widget _neomorphic() {
    final p = _p;
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: gradient == null ? p.surface : null,
        gradient: gradient,
        borderRadius: BorderRadius.circular(radius),
        boxShadow: [
          BoxShadow(color: Colors.white.withValues(alpha: 0.55), blurRadius: 10, offset: const Offset(-4, -4)),
          BoxShadow(color: AppColors.scrim(0.16), blurRadius: 10, offset: const Offset(4, 4)),
        ],
      ),
      child: child,
    );
  }

  Widget _panelBorder() {
    final p = _p;
    final r = radius.clamp(0, 8).toDouble();
    return Container(
      // The hard, unblurred offset shadow below sits almost directly behind
      // this box — an always-opaque base here keeps it pinned to its 4x5
      // sliver. A translucent [gradient] tints on TOP of that base instead
      // of replacing it, so it never lets the shadow bleed through as a
      // near-full-size dark wash (this bit us on Home's tinted cards under
      // the light panel-border packs).
      decoration: BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(r),
        border: Border.all(color: borderColor ?? p.on, width: 2.5),
        boxShadow: [BoxShadow(color: p.on, blurRadius: 0, offset: const Offset(4, 5))],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(r),
        child: Container(
          padding: padding,
          decoration: gradient == null ? null : BoxDecoration(gradient: gradient),
          child: child,
        ),
      ),
    );
  }
}

/// Faint repeating horizontal rules — the [SurfaceStyle.paperRuled] texture.
class _RuledLinesPainter extends CustomPainter {
  _RuledLinesPainter(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1;
    for (double y = 14; y < size.height; y += 14) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _RuledLinesPainter oldDelegate) => oldDelegate.color != color;
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
