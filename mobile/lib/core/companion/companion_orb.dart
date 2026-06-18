import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Advary's five living states (Sprint UI-X). The orb is the app's identity.
enum OrbState { idle, listening, speaking, celebrating, concerned }

/// A custom-painted "living spirit" orb — 80% orb, 20% face (eyes + mouth that
/// shift with mood/voice). Floats, breathes, glows, pulses, and sparks. No assets.
class CompanionOrb extends StatefulWidget {
  const CompanionOrb({super.key, this.state = OrbState.idle, this.size = 64});
  final OrbState state;
  final double size;

  @override
  State<CompanionOrb> createState() => _CompanionOrbState();
}

class _CompanionOrbState extends State<CompanionOrb> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 3600))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pad = widget.size * 0.5; // room for glow + particles
    return SizedBox(
      width: widget.size + pad,
      height: widget.size + pad,
      child: AnimatedBuilder(
        animation: _c,
        builder: (_, __) {
          final t = _c.value;
          final tau = t * 2 * math.pi;
          // float (idle) and breathe (concerned) are transforms on the whole orb.
          final dy = widget.state == OrbState.idle ? math.sin(tau) * 3.0 : 0.0;
          final scale = widget.state == OrbState.concerned ? 1 + 0.05 * math.sin(tau) : 1.0;
          return Transform.translate(
            offset: Offset(0, dy),
            child: Transform.scale(
              scale: scale,
              child: CustomPaint(painter: _OrbPainter(widget.state, t), size: Size.square(widget.size + pad)),
            ),
          );
        },
      ),
    );
  }
}

class _OrbPainter extends CustomPainter {
  _OrbPainter(this.state, this.t);
  final OrbState state;
  final double t;

  Color get _color => switch (state) {
        OrbState.listening || OrbState.speaking => AppColors.secondary,
        OrbState.celebrating => AppColors.accent,
        OrbState.concerned => const Color(0xFF6B79B0),
        OrbState.idle => AppColors.primary,
      };

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final r = size.width * 0.34;
    final tau = t * 2 * math.pi;
    final color = _color;

    // --- outer glow (bold) ---
    final glowPulse = 1 + 0.12 * math.sin(tau);
    canvas.drawCircle(
      center, r * 1.9 * glowPulse,
      Paint()
        ..color = color.withValues(alpha: state == OrbState.concerned ? 0.18 : 0.32)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 26),
    );

    // --- listening: expanding cyan ring ---
    if (state == OrbState.listening) {
      canvas.drawCircle(center, r * (1.25 + 0.12 * math.sin(tau)),
          Paint()..style = PaintingStyle.stroke..strokeWidth = 2.5..color = AppColors.secondary.withValues(alpha: 0.7));
    }
    // --- speaking: outward wave rings ---
    if (state == OrbState.speaking) {
      for (var i = 0; i < 2; i++) {
        final p = ((t + i * 0.5) % 1);
        canvas.drawCircle(center, r * (1.1 + p * 0.9),
            Paint()..style = PaintingStyle.stroke..strokeWidth = 2..color = AppColors.secondary.withValues(alpha: (1 - p) * 0.6));
      }
    }
    // --- celebrating: spark particles ---
    if (state == OrbState.celebrating) {
      final sparks = [AppColors.secondary, AppColors.primary, Colors.white, AppColors.accent];
      for (var i = 0; i < 8; i++) {
        final ang = (i / 8) * 2 * math.pi + tau * 0.3;
        final p = ((t + i * 0.12) % 1);
        final dist = r * (1.1 + p * 1.1);
        final pos = center + Offset(math.cos(ang), math.sin(ang)) * dist;
        canvas.drawCircle(pos, 3.0 * (1 - p),
            Paint()..color = sparks[i % 4].withValues(alpha: 1 - p)..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2));
      }
    }

    // --- orb body ---
    final body = Paint()
      ..shader = RadialGradient(
        center: const Alignment(-0.4, -0.5),
        colors: [Colors.white.withValues(alpha: 0.9), color, Color.lerp(color, Colors.black, 0.45)!],
        stops: const [0.0, 0.45, 1.0],
      ).createShader(Rect.fromCircle(center: center, radius: r));
    canvas.drawCircle(center, r, body);
    // rim light
    canvas.drawCircle(center, r,
        Paint()..style = PaintingStyle.stroke..strokeWidth = 1.2..color = Colors.white.withValues(alpha: 0.25));

    _drawFace(canvas, center, r, tau);
  }

  void _drawFace(Canvas canvas, Offset c, double r, double tau) {
    final ink = Paint()..color = Colors.white.withValues(alpha: 0.92)..style = PaintingStyle.fill;
    final stroke = Paint()
      ..color = Colors.white.withValues(alpha: 0.92)
      ..style = PaintingStyle.stroke
      ..strokeWidth = r * 0.07
      ..strokeCap = StrokeCap.round;

    final eyeDx = r * 0.34;
    final eyeY = c.dy - r * 0.12;
    final eyeR = r * (state == OrbState.listening ? 0.16 : 0.13);

    if (state == OrbState.concerned) {
      // softer, slightly downturned eyes
      for (final s in [-1, 1]) {
        canvas.drawCircle(Offset(c.dx + s * eyeDx, eyeY), eyeR * 0.85, ink);
      }
      // gentle frown (small upward arc -> concerned)
      final m = Rect.fromCircle(center: Offset(c.dx, c.dy + r * 0.34), radius: r * 0.26);
      canvas.drawArc(m, math.pi + 0.5, math.pi - 1.0, false, stroke);
      return;
    }

    // eyes (happy orbs); celebrating = bright, slightly bigger
    final er = state == OrbState.celebrating ? eyeR * 1.15 : eyeR;
    for (final s in [-1, 1]) {
      canvas.drawCircle(Offset(c.dx + s * eyeDx, eyeY), er, ink);
      canvas.drawCircle(Offset(c.dx + s * eyeDx - er * 0.3, eyeY - er * 0.3), er * 0.32,
          Paint()..color = Colors.white); // sparkle highlight
    }

    // mouth
    if (state == OrbState.speaking) {
      // animated open mouth (pulsing oval)
      final h = r * (0.16 + 0.12 * (0.5 + 0.5 * math.sin(tau * 2)));
      canvas.drawOval(Rect.fromCenter(center: Offset(c.dx, c.dy + r * 0.26), width: r * 0.34, height: h),
          Paint()..color = Colors.white.withValues(alpha: 0.92));
    } else {
      // smile arc (wider when celebrating)
      final w = state == OrbState.celebrating ? 0.34 : 0.28;
      final m = Rect.fromCircle(center: Offset(c.dx, c.dy + r * 0.12), radius: r * w);
      canvas.drawArc(m, 0.25, math.pi - 0.5, false, stroke);
    }
  }

  @override
  bool shouldRepaint(_OrbPainter old) => old.t != t || old.state != state;
}
