import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/auth/auth_controller.dart';
import 'core/auth/auth_state.dart';
import 'core/onboarding/companion_tour.dart';
import 'core/router/app_router.dart';
import 'core/settings/settings_repository.dart';
import 'core/theme/app_theme.dart';
import 'core/theme/theme_controller.dart';
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
        child: Stack(children: [child ?? const SizedBox.shrink(), const _VoiceBootstrap()]),
      ),
    );
  }
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
