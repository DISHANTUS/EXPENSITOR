import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Advary's five living states (Sprint UI-X). The orb is the app's identity.
enum OrbState { idle, listening, speaking, celebrating, concerned }

/// Advary's face: a custom-painted companion-bot head — glossy white dome,
/// dark visor, glowing blue eyes (with a periodic blink) and a mouth that
/// change shape with mood/voice. Floats, breathes, glows, pulses, and sparks.
/// No assets. Replaces the earlier "glossy sphere" orb (see design review at
/// the "Visor" concept) — the head material itself is deliberately theme-
/// neutral (always white/glass), while the ambient glow/ring/spark effects
/// around it stay palette-driven, same as before.
class CompanionOrb extends StatefulWidget {
  const CompanionOrb({super.key, this.state = OrbState.idle, this.size = 64, this.palette});
  final OrbState state;
  final double size;
  /// Override the palette (used by the theme picker to preview each pack's orb);
  /// defaults to the active theme.
  final AppPalette? palette;

  @override
  State<CompanionOrb> createState() => _CompanionOrbState();
}

class _CompanionOrbState extends State<CompanionOrb> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: _idleDuration())..repeat();

  /// The idle float/breathe/blink cycle speeds up or slows down with the
  /// palette's [ThemeEnergy] — `medium` (every existing pack's default) keeps
  /// today's exact 3600ms, so this is a no-op for Crimson/Aurora/Midnight/Sakura.
  Duration _idleDuration() {
    final mult = switch ((widget.palette ?? AppColors.active).energy) {
      ThemeEnergy.veryLow => 1.6,
      ThemeEnergy.low => 1.25,
      ThemeEnergy.medium => 1.0,
      ThemeEnergy.high => 0.75,
      ThemeEnergy.veryHigh => 0.55,
    };
    return Duration(milliseconds: (3600 * mult).round());
  }

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
        builder: (_, __) => CustomPaint(
          painter: _OrbPainter(widget.state, _c.value, widget.palette),
          size: Size.square(widget.size + pad),
        ),
      ),
    );
  }
}

class _OrbPainter extends CustomPainter {
  _OrbPainter(this.state, this.t, this.palette);
  final OrbState state;
  final double t;
  final AppPalette? palette;

  AppPalette get _p => palette ?? AppColors.active;

  /// Advary's eyes/mouth are a fixed signature blue — deliberately NOT
  /// palette-driven (confirmed choice), so the face reads the same across
  /// all 19 themes while the glow/ring/spark effects around it stay themed.
  static const _visorGlow = Color(0xFF29C2FF);

  Color get _ambient => switch (state) {
        OrbState.listening || OrbState.speaking => _p.secondary,
        OrbState.celebrating => _p.primary,
        OrbState.concerned => AppColors.concernedOf(_p.primary),
        OrbState.idle => _p.primary,
      };

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final r = size.width * 0.29; // head "radius" reference unit
    final tau = t * 2 * math.pi;
    final ambient = _ambient;

    final floaty = state == OrbState.idle || state == OrbState.listening;
    final dy = floaty ? math.sin(tau) * r * 0.11 : 0.0;
    final breathScale = state == OrbState.concerned ? 1 + 0.05 * math.sin(tau) : 1.0;
    final headCenter = Offset(center.dx, center.dy + dy);

    // --- grounding shadow: fixed position, does NOT float with the head ---
    final shadowPulse = floaty ? (0.5 - 0.5 * math.sin(tau)) : 0.5; // opposite phase to dy
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(center.dx, center.dy + r * 1.5),
        width: r * 1.5 * (0.86 + 0.14 * shadowPulse),
        height: r * 0.32 * (0.86 + 0.14 * shadowPulse),
      ),
      Paint()
        ..color = AppColors.scrim(0.28 + 0.12 * shadowPulse)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8),
    );

    // --- ambient glow (theme colored, behind the head) ---
    final glowPulse = 1 + 0.12 * math.sin(tau);
    canvas.drawCircle(
      headCenter,
      r * 1.7 * glowPulse,
      Paint()
        ..color = ambient.withValues(alpha: state == OrbState.concerned ? 0.14 : 0.24)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 22),
    );

    // --- listening: expanding ring ---
    if (state == OrbState.listening) {
      canvas.drawCircle(headCenter, r * (1.15 + 0.12 * math.sin(tau)),
          Paint()..style = PaintingStyle.stroke..strokeWidth = 2.2..color = ambient.withValues(alpha: 0.65));
    }
    // --- speaking: outward wave rings ---
    if (state == OrbState.speaking) {
      for (var i = 0; i < 2; i++) {
        final p = ((t + i * 0.5) % 1);
        canvas.drawCircle(headCenter, r * (1.05 + p * 0.85),
            Paint()..style = PaintingStyle.stroke..strokeWidth = 2..color = ambient.withValues(alpha: (1 - p) * 0.55));
      }
    }
    // --- celebrating: spark particles ---
    if (state == OrbState.celebrating) {
      final sparks = [_p.spark, _p.primary, Colors.white, _p.secondary];
      for (var i = 0; i < 8; i++) {
        final ang = (i / 8) * 2 * math.pi + tau * 0.3;
        final p = ((t + i * 0.12) % 1);
        final dist = r * (1.0 + p * 1.0);
        final pos = headCenter + Offset(math.cos(ang), math.sin(ang)) * dist;
        canvas.drawCircle(pos, 2.6 * (1 - p),
            Paint()..color = sparks[i % 4].withValues(alpha: 1 - p)..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2));
      }
    }

    // --- the head itself, translated by the float offset + concerned breathing ---
    canvas.save();
    canvas.translate(headCenter.dx, headCenter.dy);
    canvas.scale(breathScale);
    _drawHead(canvas, r);
    canvas.restore();
  }

  void _drawHead(Canvas canvas, double r) {
    final w = r * 2.2, h = r * 2.0;
    final rect = Rect.fromCenter(center: Offset.zero, width: w, height: h);
    final headRRect = RRect.fromRectAndCorners(
      rect,
      topLeft: Radius.elliptical(w * 0.5, h * 0.62),
      topRight: Radius.elliptical(w * 0.5, h * 0.62),
      bottomLeft: Radius.elliptical(w * 0.46, h * 0.40),
      bottomRight: Radius.elliptical(w * 0.46, h * 0.40),
    );
    final headPath = Path()..addRRect(headRRect);

    final body = Paint()
      ..shader = const RadialGradient(
        center: Alignment(-0.36, -0.62),
        colors: [Color(0xFFFFFFFF), Color(0xFFEEF0F4), Color(0xFFD6DAE2), Color(0xFFC1C6D0)],
        stops: [0.0, 0.34, 0.68, 1.0],
      ).createShader(rect);
    canvas.drawPath(headPath, body);
    canvas.drawPath(
      headPath,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = Colors.white.withValues(alpha: 0.5),
    );

    _drawVisor(canvas, w, h);
  }

  void _drawVisor(Canvas canvas, double headW, double headH) {
    final vw = headW * 0.78, vh = headH * 0.5;
    final vRect = Rect.fromCenter(center: Offset(0, -headH * 0.02), width: vw, height: vh);
    final visorPath = Path()..addRRect(RRect.fromRectAndRadius(vRect, Radius.circular(vh * 0.5)));

    canvas.save();
    canvas.clipPath(visorPath);
    canvas.drawRect(
      vRect.inflate(2),
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF0D0E12), Color(0xFF020203)],
        ).createShader(vRect),
    );
    _drawEyesAndMouth(canvas, vRect);
    canvas.restore();

    canvas.drawPath(
      visorPath,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = Colors.white.withValues(alpha: 0.08),
    );
  }

  void _drawEyesAndMouth(Canvas canvas, Rect visor) {
    final concerned = state == OrbState.concerned;
    final celebrating = state == OrbState.celebrating;
    final speaking = state == OrbState.speaking;

    // Real blinks are quick (~150ms) and infrequent — synced to the same
    // idle cycle as the float/breathe motion, one blink per lap. Concerned
    // eyes stay narrowed instead of blinking (a distinct, "tired" read).
    final blink = concerned ? 1.0 : _blinkScale(t);
    final eyeW = visor.width * 0.21;
    final eyeH = (concerned ? visor.height * 0.30 : visor.height * (celebrating ? 0.62 : 0.50)) * blink;
    final eyeY = visor.top + visor.height * 0.33;
    final eyeDx = visor.width * 0.27;
    final eyeColor = concerned ? Color.lerp(_visorGlow, Colors.black, 0.35)! : _visorGlow;
    final eyeAlpha = concerned ? 0.55 : 1.0;

    for (final side in [-1.0, 1.0]) {
      final cx = visor.center.dx + side * eyeDx;
      final rect = Rect.fromCenter(center: Offset(cx, eyeY), width: eyeW, height: math.max(eyeH, 1.2));
      final rr = RRect.fromRectAndRadius(rect, Radius.circular(eyeW * 0.4));
      canvas.drawRRect(
        rr,
        Paint()
          ..color = eyeColor.withValues(alpha: eyeAlpha)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3),
      );
      canvas.drawRRect(rr, Paint()..color = eyeColor.withValues(alpha: eyeAlpha));
    }

    // mouth
    final mouthStroke = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = visor.height * 0.09
      ..strokeCap = StrokeCap.round
      ..color = _visorGlow;
    final mw = visor.width * (celebrating ? 0.42 : 0.30);
    final mouthCenter = Offset(visor.center.dx, visor.top + visor.height * 0.80);

    if (speaking) {
      final h = visor.height * (0.10 + 0.10 * (0.5 + 0.5 * math.sin(t * 2 * math.pi * 3)));
      canvas.drawOval(Rect.fromCenter(center: mouthCenter, width: mw * 0.5, height: h),
          Paint()..color = _visorGlow);
    } else if (concerned) {
      final m = Rect.fromCenter(center: Offset(mouthCenter.dx, mouthCenter.dy + visor.height * 0.12), width: mw, height: mw);
      canvas.drawArc(m, math.pi + 0.5, math.pi - 1.0, false, mouthStroke..color = _visorGlow.withValues(alpha: 0.55));
    } else {
      final m = Rect.fromCenter(center: Offset(mouthCenter.dx, mouthCenter.dy - visor.height * 0.06), width: mw, height: mw);
      canvas.drawArc(m, 0.25, math.pi - 0.5, false, mouthStroke);
    }
  }

  /// Open almost the entire cycle; a quick close-and-open near the end.
  double _blinkScale(double p) {
    if (p < 0.88) return 1.0;
    if (p < 0.92) return 1.0 - (p - 0.88) / 0.04 * 0.94;
    if (p < 0.96) return 0.06 + (p - 0.92) / 0.04 * 0.94;
    return 1.0;
  }

  @override
  bool shouldRepaint(_OrbPainter old) => old.t != t || old.state != state || old.palette != palette;
}
