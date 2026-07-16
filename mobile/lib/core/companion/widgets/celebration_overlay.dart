import 'dart:async';
import 'dart:math';

import 'package:confetti/confetti.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../theme/app_theme.dart';
import '../../theme/vitality.dart';
import '../reaction.dart';
import '../reaction_queue.dart';

/// Fires a celebration whenever a milestone/achievement reaction surfaces
/// (Sprint UI-X, extended for the 15-theme rollout). Global — sits over every
/// screen via CompanionScaffold. Most themes keep the aurora confetti burst
/// (already theme-coloured via `AppColors`); a couple of themes swap it for
/// their own visual language instead — one new branch here, not a separate
/// reaction engine per financial event type.
class CelebrationOverlay extends ConsumerStatefulWidget {
  const CelebrationOverlay({super.key});
  @override
  ConsumerState<CelebrationOverlay> createState() => _CelebrationOverlayState();
}

class _CelebrationOverlayState extends ConsumerState<CelebrationOverlay> {
  late final ConfettiController _c = ConfettiController(duration: const Duration(milliseconds: 1200));
  String? _lastSig;
  bool _themedFlash = false;
  Timer? _flashTimer;

  @override
  void dispose() {
    _c.dispose();
    _flashTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final id = AppColors.active.id;
    ref.listen(reactionQueueProvider, (_, next) {
      final r = next.isEmpty ? null : next.first;
      if (r == null || r.importance == ReactionImportance.normal || r.signature == _lastSig) return;
      _lastSig = r.signature;
      if (id == 'comic' || id == 'terminal') {
        _flashTimer?.cancel();
        setState(() => _themedFlash = true);
        _flashTimer = Timer(const Duration(milliseconds: 1100), () {
          if (mounted) setState(() => _themedFlash = false);
        });
      } else {
        _c.play();
      }
    });

    if (id == 'comic') {
      // The shared Positioned host (companion_scaffold.dart) only pins
      // top/left/right — no `bottom`, so it shrink-wraps to content height.
      // Give this flash its own height so Center has room to work.
      final p = AppColors.active;
      return IgnorePointer(
        child: SizedBox(
          height: 220,
          child: Center(
            child: AnimatedOpacity(
              opacity: _themedFlash ? 1 : 0,
              duration: const Duration(milliseconds: 200),
              child: HalftoneDots(
                color: p.primary,
                child: Text('POW!',
                    style: TextStyle(fontSize: 52, fontWeight: FontWeight.w900, color: p.primary,
                        shadows: [Shadow(color: p.on, offset: const Offset(3, 3))])),
              ),
            ),
          ),
        ),
      );
    }
    if (id == 'terminal') {
      final p = AppColors.active;
      return IgnorePointer(
        child: AnimatedOpacity(
          opacity: _themedFlash ? 1 : 0,
          duration: const Duration(milliseconds: 120),
          child: DecoratedBox(decoration: BoxDecoration(color: p.primary.withValues(alpha: 0.05))),
        ),
      );
    }

    return IgnorePointer(
      child: Align(
        alignment: Alignment.topCenter,
        child: ConfettiWidget(
          confettiController: _c,
          blastDirection: pi / 2,          // downward
          emissionFrequency: 0.06,
          numberOfParticles: 16,
          maxBlastForce: 20,
          minBlastForce: 8,
          gravity: 0.25,
          shouldLoop: false,
          colors: [AppColors.primary, AppColors.accent, AppColors.spark, Colors.white],
        ),
      ),
    );
  }
}
