import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_controller.dart';
import '../router/app_router.dart';
import '../voice/voice_service.dart';
import 'tour_repository.dart';

class TourState {
  const TourState({
    this.active = false,
    this.loading = false,
    this.steps = const [],
    this.index = 0,
    this.companionName = 'Advary',
  });

  final bool active;
  final bool loading;
  final List<TourStep> steps;
  final int index;
  final String companionName;

  TourStep? get current => (active && index >= 0 && index < steps.length) ? steps[index] : null;
  bool get isLast => index >= steps.length - 1;
  bool get isFirst => index <= 0;

  TourState copyWith({bool? active, bool? loading, List<TourStep>? steps, int? index, String? companionName}) =>
      TourState(
        active: active ?? this.active,
        loading: loading ?? this.loading,
        steps: steps ?? this.steps,
        index: index ?? this.index,
        companionName: companionName ?? this.companionName,
      );
}

/// Drives the Advary-led first-launch walkthrough: fetches the steps, navigates
/// the real app to each screen, narrates (if the voice setting is on), and stamps
/// the tour as seen on finish/skip.
class TourController extends Notifier<TourState> {
  bool _offered = false;   // guards the first-login auto-start within a session

  @override
  TourState build() => const TourState();

  /// First-login gate: launch once if the user hasn't seen it. Safe to call on
  /// every auth change — it no-ops once offered or while active.
  void autoStartIfNeeded() {
    final user = ref.read(authControllerProvider).user;
    if (_offered || state.active || user == null || user.hasSeenTour) return;
    _offered = true;
    start();
  }

  /// Launch (or replay) the tour from the top.
  Future<void> start() async {
    if (state.loading) return;
    state = state.copyWith(loading: true);
    try {
      final tour = await ref.read(tourRepositoryProvider).fetch();
      if (tour.steps.isEmpty) {
        state = state.copyWith(loading: false);
        return;
      }
      state = TourState(
        active: true, loading: false, steps: tour.steps, index: 0, companionName: tour.companionName);
      _arrive();
    } catch (_) {
      state = state.copyWith(loading: false);   // offline / error → just don't show it
    }
  }

  void next() {
    if (!state.active) return;
    if (state.isLast) {
      finish();
    } else {
      state = state.copyWith(index: state.index + 1);
      _arrive();
    }
  }

  void back() {
    if (!state.active || state.isFirst) return;
    state = state.copyWith(index: state.index - 1);
    _arrive();
  }

  void skip() => _dismiss();

  /// Completing the tour pushes the user straight into Budget Setup — "let's get
  /// to know you so I can build a realistic plan."
  void finish() {
    _dismiss();
    try {
      ref.read(routerProvider).go('/budget-setup');
    } catch (_) {/* router not ready */}
  }

  /// Navigate to the current step's screen. Narration is handled by the overlay
  /// widget (which can read the autoDispose voice settings safely).
  void _arrive() {
    final step = state.current;
    if (step == null) return;
    try {
      ref.read(routerProvider).go(step.route);
    } catch (_) {/* router not ready */}
  }

  void _dismiss() {
    try {
      ref.read(voiceControllerProvider.notifier).stop();
    } catch (_) {/* voice not initialised */}
    state = const TourState();
    ref.read(authControllerProvider.notifier).markTourSeen();
    // Best-effort server stamp (never throws).
    ref.read(tourRepositoryProvider).markComplete();
  }
}

final tourControllerProvider =
    NotifierProvider<TourController, TourState>(TourController.new);
