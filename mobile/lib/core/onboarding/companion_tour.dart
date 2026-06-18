import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_controller.dart';
import '../auth/auth_state.dart';
import '../companion/companion_orb.dart';
import '../settings/settings_repository.dart';
import '../voice/voice_service.dart';
import 'tour_controller.dart';

/// Mounted once at the app root (above the router). Stacks the live walkthrough
/// over whatever screen is showing, and launches it on first login.
class TourHost extends ConsumerStatefulWidget {
  const TourHost({super.key, required this.child});
  final Widget child;

  @override
  ConsumerState<TourHost> createState() => _TourHostState();
}

class _TourHostState extends ConsumerState<TourHost> {
  @override
  Widget build(BuildContext context) {
    // Watch (not just listen) so we catch the transition no matter the timing of
    // session restore vs. fresh login. autoStartIfNeeded is idempotent (guarded by
    // _offered + hasSeenTour), so scheduling it on each authenticated build is safe.
    final auth = ref.watch(authControllerProvider);
    if (auth.status == AuthStatus.authenticated && (auth.user?.hasSeenTour == false)) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) ref.read(tourControllerProvider.notifier).autoStartIfNeeded();
      });
    }

    final active = ref.watch(tourControllerProvider.select((s) => s.active));
    return Stack(
      children: [
        widget.child,
        if (active) const Positioned.fill(child: _TourOverlay()),
      ],
    );
  }
}

class _TourOverlay extends ConsumerStatefulWidget {
  const _TourOverlay();

  @override
  ConsumerState<_TourOverlay> createState() => _TourOverlayState();
}

class _TourOverlayState extends ConsumerState<_TourOverlay> {
  String? _spokenKey;   // the step we last narrated, so we don't repeat it
  final _nameCtrl = TextEditingController();

  @override
  void dispose() {
    _nameCtrl.dispose();
    super.dispose();
  }

  /// Save what the user wants to be called (best-effort) then advance.
  Future<void> _saveNameThenNext() async {
    final name = _nameCtrl.text.trim();
    if (name.isNotEmpty) {
      try {
        await ref.read(settingsRepositoryProvider).setDisplayName(name);
        ref.invalidate(userSettingsProvider);
      } catch (_) {/* don't block onboarding on a failed save */}
    }
    if (mounted) ref.read(tourControllerProvider.notifier).next();
  }

  /// Narrate a step aloud only if the user opted into spoken greetings.
  void _maybeNarrate(String key, String spokenText) {
    if (key == _spokenKey || spokenText.trim().isEmpty) return;
    final prefs = ref.read(userSettingsProvider).valueOrNull?.notificationPreferences ?? const {};
    if (!(prefs['speak_greeting_on_open'] ?? false) || (prefs['voice_when_tapped_only'] ?? false)) return;
    _spokenKey = key;
    ref.read(voiceControllerProvider.notifier).speak(spokenText, pitch: 1.05);
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(tourControllerProvider);
    final n = ref.read(tourControllerProvider.notifier);
    final step = s.current;
    if (step == null) return const SizedBox.shrink();
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeNarrate(step.key, step.spokenText));

    final speaking = ref.watch(voiceControllerProvider) == VoiceState.speaking;

    // Non-modal: a light dim keeps the real screen visible while the companion
    // bubble sits at the top and narrates. Tapping the dim is absorbed.
    return Material(
      type: MaterialType.transparency,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () {},
        child: Container(
          color: const Color(0x4D090D18),               // ~30% dim — screen stays readable
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 96),                // clear the app bar
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Container(
                  decoration: BoxDecoration(
                    color: const Color(0xF21A2236),
                    borderRadius: BorderRadius.circular(22),
                    border: Border.all(color: const Color(0x26FFFFFF)),
                    boxShadow: const [BoxShadow(color: Color(0x66000000), blurRadius: 22, offset: Offset(0, 10))],
                  ),
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          CompanionOrb(state: speaking ? OrbState.speaking : OrbState.idle, size: 42),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(step.title,
                                style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      AnimatedSwitcher(
                        duration: const Duration(milliseconds: 320),
                        transitionBuilder: (child, anim) => FadeTransition(opacity: anim, child: child),
                        child: Text(step.narration,
                            key: ValueKey(step.key),
                            style: const TextStyle(color: Color(0xF2FFFFFF), fontSize: 15, height: 1.4)),
                      ),
                      if (step.key == 'welcome') ...[
                        const SizedBox(height: 14),
                        const Text('What should I call you?',
                            style: TextStyle(color: Color(0xCCFFFFFF), fontSize: 13)),
                        const SizedBox(height: 6),
                        TextField(
                          controller: _nameCtrl,
                          style: const TextStyle(color: Colors.white),
                          cursorColor: const Color(0xFF7C5CFF),
                          decoration: InputDecoration(
                            hintText: 'Your name',
                            hintStyle: const TextStyle(color: Color(0x66FFFFFF)),
                            isDense: true,
                            filled: true,
                            fillColor: Colors.white.withValues(alpha: 0.06),
                            enabledBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: const BorderSide(color: Color(0x26FFFFFF))),
                            focusedBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: const BorderSide(color: Color(0xFF7C5CFF))),
                          ),
                        ),
                      ],
                      const SizedBox(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          _Dots(count: s.steps.length, index: s.index),
                          Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              if (!s.isFirst) _TourButton(label: 'Back', onTap: n.back),
                              _TourButton(label: s.isLast ? 'Done' : 'Skip', onTap: n.skip),
                              const SizedBox(width: 4),
                              _TourButton(
                                  label: s.isLast ? "Let's go" : 'Next',
                                  onTap: step.key == 'welcome' ? _saveNameThenNext : n.next,
                                  primary: true),
                            ],
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Progress dots — filled up to the current step (explicit colors so they render
/// reliably in the app-level overlay).
class _Dots extends StatelessWidget {
  const _Dots({required this.count, required this.index});
  final int count;
  final int index;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < count; i++)
          AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            margin: const EdgeInsets.only(right: 5),
            width: i == index ? 16 : 6,
            height: 6,
            decoration: BoxDecoration(
              color: i <= index ? const Color(0xFF7C5CFF) : const Color(0x33FFFFFF),
              borderRadius: BorderRadius.circular(3),
            ),
          ),
      ],
    );
  }
}

/// A tappable pill button drawn with explicit styles (no Theme/Material text
/// dependency) so it renders reliably in the app-level tour overlay.
class _TourButton extends StatelessWidget {
  const _TourButton({required this.label, required this.onTap, this.primary = false});
  final String label;
  final VoidCallback onTap;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        margin: const EdgeInsets.only(left: 4),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 11),
        decoration: BoxDecoration(
          color: primary ? const Color(0xFF7C5CFF) : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Text(label,
            style: TextStyle(
              color: primary ? Colors.white : const Color(0xFF9B8CFF),
              fontWeight: FontWeight.w600,
              fontSize: 15,
            )),
      ),
    );
  }
}
