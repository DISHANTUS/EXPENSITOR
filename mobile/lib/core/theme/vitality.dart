import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app_theme.dart';
import 'theme_controller.dart';

/// The "feels alive" toolkit — small, reusable ambient-motion widgets a
/// theme's [MotionProfile] opts into (idle wobble, a breathing glow, moving
/// stripes, a blinking cursor, a typewriter reveal), plus a couple of static
/// decorative textures (scanlines, halftone dots). Every animated widget here
/// reuses the same `AnimationController` + `AnimatedBuilder` + trig-math shape
/// already used elsewhere in this app (Home's `_BreathingToday`/`_LivingMarker`)
/// — this file just makes that pattern reusable and theme-aware, instead of
/// re-implementing it once per screen.
///
/// All animated widgets here respect [Vitality.amplitudeFor]: the OS
/// "reduce motion" accessibility flag always wins (forces static), otherwise
/// the user's [MotionIntensity] preference scales the motion.
class Vitality {
  const Vitality._();

  static double amplitudeFor(BuildContext context, WidgetRef ref) {
    if (MediaQuery.of(context).disableAnimations) return 0;
    return switch (ref.watch(motionIntensityProvider)) {
      MotionIntensity.off => 0,
      MotionIntensity.minimal => 0.5,
      MotionIntensity.normal => 1.0,
      MotionIntensity.dynamic => 1.4,
    };
  }
}

/// A gentle rotate oscillation — a bobblehead wobble. Wrap the companion
/// avatar or an icon in it.
class IdleWobble extends ConsumerStatefulWidget {
  const IdleWobble({
    super.key,
    required this.child,
    this.amplitudeDeg = 4,
    this.period = const Duration(milliseconds: 3400),
  });
  final Widget child;
  final double amplitudeDeg;
  final Duration period;

  @override
  ConsumerState<IdleWobble> createState() => _IdleWobbleState();
}

class _IdleWobbleState extends ConsumerState<IdleWobble> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: widget.period)..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final amp = Vitality.amplitudeFor(context, ref);
    if (amp == 0) return widget.child;
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) {
        final deg = math.sin(_c.value * 2 * math.pi) * widget.amplitudeDeg * amp;
        return Transform.rotate(angle: deg * math.pi / 180, child: widget.child);
      },
    );
  }
}

/// A slow scale + glow pulse — generalizes Home's `_BreathingToday` idiom so
/// any card/badge can "breathe".
class BreathingGlow extends ConsumerStatefulWidget {
  const BreathingGlow({
    super.key,
    required this.child,
    this.color,
    this.period = const Duration(milliseconds: 2600),
    this.scaleAmount = 0.04,
    this.borderRadius = 20,
  });
  final Widget child;
  final Color? color;
  final Duration period;
  final double scaleAmount;
  final double borderRadius;

  @override
  ConsumerState<BreathingGlow> createState() => _BreathingGlowState();
}

class _BreathingGlowState extends ConsumerState<BreathingGlow> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: widget.period)..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final amp = Vitality.amplitudeFor(context, ref);
    final glowColor = widget.color ?? AppColors.primary;
    if (amp == 0) return widget.child;
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) {
        final t = Curves.easeInOut.transform(_c.value);
        return Transform.scale(
          scale: 1 + widget.scaleAmount * amp * t,
          child: DecoratedBox(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(widget.borderRadius),
              boxShadow: [
                BoxShadow(color: glowColor.withValues(alpha: 0.35 * amp * t), blurRadius: 18 * (0.5 + t), spreadRadius: 1),
              ],
            ),
            child: widget.child,
          ),
        );
      },
    );
  }
}

/// A scrolling diagonal-stripe background behind [child] — the Flutter
/// equivalent of the Bootstrap-style animated CSS stripe trick validated on
/// the Comic prototype's "Ask Advary" button (Comic, Velocity, Riot).
class MovingStripeBackground extends ConsumerStatefulWidget {
  const MovingStripeBackground({
    super.key,
    required this.child,
    this.stripeColor,
    this.pitch = 16,
    this.angle = -0.5,
    this.period = const Duration(milliseconds: 900),
  });
  final Widget child;
  final Color? stripeColor;
  final double pitch;
  final double angle; // radians
  final Duration period;

  @override
  ConsumerState<MovingStripeBackground> createState() => _MovingStripeBackgroundState();
}

class _MovingStripeBackgroundState extends ConsumerState<MovingStripeBackground> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: widget.period)..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final amp = Vitality.amplitudeFor(context, ref);
    final color = widget.stripeColor ?? Colors.white.withValues(alpha: 0.2);
    if (amp == 0) {
      return ClipRect(child: Stack(children: [
        Positioned.fill(child: CustomPaint(painter: _StripePainter(0, color, widget.pitch, widget.angle))),
        widget.child,
      ]));
    }
    return ClipRect(
      child: Stack(children: [
        Positioned.fill(
          child: AnimatedBuilder(
            animation: _c,
            builder: (_, __) => CustomPaint(painter: _StripePainter(_c.value * amp, color, widget.pitch, widget.angle)),
          ),
        ),
        widget.child,
      ]),
    );
  }
}

class _StripePainter extends CustomPainter {
  _StripePainter(this.t, this.color, this.pitch, this.angle);
  final double t;
  final Color color;
  final double pitch;
  final double angle;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = pitch * 0.4;
    final diag = size.width + size.height;
    final offset = (t * pitch) % pitch;
    canvas.save();
    canvas.translate(size.width / 2, size.height / 2);
    canvas.rotate(angle);
    for (double x = -diag + offset; x < diag; x += pitch) {
      canvas.drawLine(Offset(x, -diag), Offset(x, diag), paint);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _StripePainter old) => old.t != t || old.color != color;
}

/// A blinking text-cursor block — Terminal's signature.
class BlinkingCursor extends ConsumerStatefulWidget {
  const BlinkingCursor({super.key, this.width = 8, this.height = 16, this.color});
  final double width;
  final double height;
  final Color? color;

  @override
  ConsumerState<BlinkingCursor> createState() => _BlinkingCursorState();
}

class _BlinkingCursorState extends ConsumerState<BlinkingCursor> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1000))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final amp = Vitality.amplitudeFor(context, ref);
    final color = widget.color ?? AppColors.primary;
    final block = Container(width: widget.width, height: widget.height, color: color);
    if (amp == 0) return block;
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) => Opacity(opacity: _c.value < 0.5 ? 1 : 0, child: block),
    );
  }
}

/// Reveals [text] one character at a time — Terminal's typewriter greeting.
/// Jumps straight to the full text when motion is off.
class TypewriterText extends ConsumerStatefulWidget {
  const TypewriterText(this.text, {super.key, this.style, this.speed = const Duration(milliseconds: 32), this.onDone});
  final String text;
  final TextStyle? style;
  final Duration speed;
  final VoidCallback? onDone;

  @override
  ConsumerState<TypewriterText> createState() => _TypewriterTextState();
}

class _TypewriterTextState extends ConsumerState<TypewriterText> {
  int _shown = 0;
  Timer? _timer;
  bool _started = false;

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _start() {
    if (_started) return;
    _started = true;
    if (Vitality.amplitudeFor(context, ref) == 0) {
      setState(() => _shown = widget.text.length);
      widget.onDone?.call();
      return;
    }
    _timer = Timer.periodic(widget.speed, (t) {
      if (!mounted) {
        t.cancel();
        return;
      }
      setState(() => _shown++);
      if (_shown >= widget.text.length) {
        t.cancel();
        widget.onDone?.call();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    WidgetsBinding.instance.addPostFrameCallback((_) => _start());
    return Text(widget.text.substring(0, _shown.clamp(0, widget.text.length)), style: widget.style);
  }
}

/// A money/number count-up — matches the `TweenAnimationBuilder<double>`
/// idiom Home's `_ElevatedDate` already uses for its scale-pop. Nothing like
/// this existed anywhere in the app before this file.
class CountUpText extends ConsumerWidget {
  const CountUpText({super.key, required this.value, this.style, this.duration = const Duration(milliseconds: 900), this.formatter});
  final double value;
  final TextStyle? style;
  final Duration duration;
  final String Function(double)? formatter;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final amp = Vitality.amplitudeFor(context, ref);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: value),
      duration: amp == 0 ? Duration.zero : duration,
      curve: Curves.easeOutCubic,
      builder: (_, v, __) => Text(formatter?.call(v) ?? v.round().toString(), style: style),
    );
  }
}

/// A faint static scanline texture over [child] — Terminal/Cyberpunk. Purely
/// decorative (no controller), so it's cheap and always renders.
class ScanlineOverlay extends StatelessWidget {
  const ScanlineOverlay({super.key, required this.child, this.color});
  final Widget child;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final c = color ?? AppColors.primary;
    return Stack(children: [
      child,
      Positioned.fill(child: IgnorePointer(child: CustomPaint(painter: _ScanlinesPainter(c)))),
    ]);
  }
}

class _ScanlinesPainter extends CustomPainter {
  _ScanlinesPainter(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color.withValues(alpha: 0.06)
      ..strokeWidth = 1;
    for (double y = 0; y < size.height; y += 3) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _ScanlinesPainter old) => old.color != color;
}

/// A faint static halftone-dot texture over [child] — Comic/Riot/Pop.
/// Purely decorative (no controller).
class HalftoneDots extends StatelessWidget {
  const HalftoneDots({super.key, required this.child, this.color, this.spacing = 7, this.dotRadius = 1.1, this.opacity = 0.08});
  final Widget child;
  final Color? color;
  final double spacing;
  final double dotRadius;
  final double opacity;

  @override
  Widget build(BuildContext context) {
    final c = color ?? AppColors.on;
    return Stack(children: [
      Positioned.fill(
        child: IgnorePointer(child: CustomPaint(painter: _HalftonePainter(c.withValues(alpha: opacity), spacing, dotRadius))),
      ),
      child,
    ]);
  }
}

class _HalftonePainter extends CustomPainter {
  _HalftonePainter(this.color, this.spacing, this.r);
  final Color color;
  final double spacing;
  final double r;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color;
    for (double y = 0; y < size.height; y += spacing) {
      for (double x = 0; x < size.width; x += spacing) {
        canvas.drawCircle(Offset(x, y), r, paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _HalftonePainter old) => old.color != color || old.spacing != spacing || old.r != r;
}
