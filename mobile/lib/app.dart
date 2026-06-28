import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/auth/auth_controller.dart';
import 'core/auth/auth_state.dart';
import 'core/onboarding/companion_tour.dart';
import 'core/router/app_router.dart';
import 'core/settings/settings_repository.dart';
import 'core/theme/app_theme.dart';
import 'core/theme/theme_controller.dart';
import 'core/voice/conversation_controller.dart';
import 'core/voice/device_voices.dart';
import 'core/voice/voice_service.dart';

class ExpensitorApp extends ConsumerWidget {
  const ExpensitorApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    ref.watch(themeProvider);   // re-skin the whole app when the theme pack changes
    return MaterialApp.router(
      title: 'Expensitor',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark(),
      darkTheme: AppTheme.dark(),
      themeMode: ThemeMode.dark,
      routerConfig: router,
      // The first-launch guided tour sits above every screen and navigates the
      // real app while Advary narrates. _VoiceBootstrap (zero-size) re-applies the
      // user's chosen device voice once settings load.
      builder: (context, child) => TourHost(
        child: Stack(children: [
          child ?? const SizedBox.shrink(),
          const _VoiceBootstrap(),
          const _AudioLifeguard(),
        ]),
      ),
    );
  }
}

/// Releases the mic + speaker whenever the app leaves the foreground. Without this,
/// a voice session left open when the user switches apps keeps the audio session —
/// and a live mic leaves Android in "communication mode", silencing the user's
/// ringtones and notifications until the app is killed. Renders nothing.
class _AudioLifeguard extends ConsumerStatefulWidget {
  const _AudioLifeguard();

  @override
  ConsumerState<_AudioLifeguard> createState() => _AudioLifeguardState();
}

class _AudioLifeguardState extends ConsumerState<_AudioLifeguard> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Only act on truly leaving the foreground (paused/hidden). NOT on `inactive`,
    // which fires for transient overlays — the notification shade, the app switcher,
    // and (critically) the runtime mic-permission dialog — where cancelling STT
    // would break the first-time permission grant.
    if (state != AppLifecycleState.paused && state != AppLifecycleState.hidden) return;
    try {
      ref.read(voiceControllerProvider.notifier).stop();
    } catch (_) {/* voice not ready */}
    try {
      ref.read(conversationControllerProvider.notifier).close();
    } catch (_) {/* conversation not ready */}
  }

  @override
  Widget build(BuildContext context) => const SizedBox.shrink();
}

/// Re-applies the saved device TTS voice on launch so the companion keeps the
/// voice the user chose in Voice Studio. Renders nothing.
class _VoiceBootstrap extends ConsumerWidget {
  const _VoiceBootstrap();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Only touch settings once authenticated (avoids a pre-login 401 that would
    // leave the provider stuck in an error state).
    if (ref.watch(authControllerProvider).status == AuthStatus.authenticated) {
      ref.listen(userSettingsProvider, (_, next) {
        final s = next.valueOrNull;
        final engine = ref.read(ttsEngineProvider);
        if (s != null && engine is FlutterTtsEngine && (s.selectedVoice ?? '').isNotEmpty) {
          engine.useVoice(DeviceVoice(name: s.selectedVoice!, locale: s.voiceLocale ?? ''));
        }
      });
      ref.watch(userSettingsProvider);   // ensure the settings load fires
    }
    return const SizedBox.shrink();
  }
}
