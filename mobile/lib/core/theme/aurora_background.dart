import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'app_theme.dart';

/// A slow, living aurora field painted behind every screen (Sprint UI-X). Three
/// soft blobs (violet / cyan / pink) drift on a long loop over the dark base.
class AuroraBackground extends StatefulWidget {
  const AuroraBackground({super.key, this.child, this.intensity = 1.0});
  final Widget? child;
  final double intensity;   // 1.0 = bold (default); lower = calmer

  @override
  State<AuroraBackground> createState() => _AuroraBackgroundState();
}

class _AuroraBackgroundState extends State<AuroraBackground> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(seconds: 18))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        const Positioned.fill(child: ColoredBox(color: AppColors.bg)),
        Positioned.fill(
          child: RepaintBoundary(
            child: AnimatedBuilder(
              animation: _c,
              builder: (_, __) => CustomPaint(painter: _AuroraPainter(_c.value, widget.intensity)),
            ),
          ),
        ),
        if (widget.child != null) Positioned.fill(child: widget.child!),
      ],
    );
  }
}

class _AuroraPainter extends CustomPainter {
  _AuroraPainter(this.t, this.intensity);
  final double t;
  final double intensity;

  void _blob(Canvas c, Size s, Color color, double cx, double cy, double r) {
    final paint = Paint()
      ..shader = RadialGradient(colors: [color.withValues(alpha: 0.55 * intensity), color.withValues(alpha: 0)])
          .createShader(Rect.fromCircle(center: Offset(cx, cy), radius: r))
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 60);
    c.drawCircle(Offset(cx, cy), r, paint);
  }

  @override
  void paint(Canvas c, Size s) {
    final a = t * 2 * math.pi;
    _blob(c, s, AppColors.primary, s.width * (0.2 + 0.1 * math.sin(a)), s.height * (0.18 + 0.06 * math.cos(a)), s.width * 0.7);
    _blob(c, s, AppColors.secondary, s.width * (0.85 + 0.08 * math.cos(a * 0.9)), s.height * (0.3 + 0.07 * math.sin(a * 1.1)), s.width * 0.6);
    _blob(c, s, AppColors.accent, s.width * (0.3 + 0.1 * math.cos(a * 1.2)), s.height * (0.85 + 0.05 * math.sin(a)), s.width * 0.65);
  }

  @override
  bool shouldRepaint(_AuroraPainter old) => old.t != t || old.intensity != intensity;
}
