import 'dart:math';

import 'package:confetti/confetti.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../theme/app_theme.dart';
import '../reaction.dart';
import '../reaction_queue.dart';

/// Fires aurora confetti whenever a milestone/achievement reaction surfaces
/// (Sprint UI-X). Global — sits over every screen via CompanionScaffold.
class CelebrationOverlay extends ConsumerStatefulWidget {
  const CelebrationOverlay({super.key});
  @override
  ConsumerState<CelebrationOverlay> createState() => _CelebrationOverlayState();
}

class _CelebrationOverlayState extends ConsumerState<CelebrationOverlay> {
  late final ConfettiController _c = ConfettiController(duration: const Duration(milliseconds: 1200));
  String? _lastSig;

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(reactionQueueProvider, (_, next) {
      final r = next.isEmpty ? null : next.first;
      if (r != null && r.importance != ReactionImportance.normal && r.signature != _lastSig) {
        _lastSig = r.signature;
        _c.play();
      }
    });
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
