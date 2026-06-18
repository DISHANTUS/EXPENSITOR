import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/companion/companion_orb.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/settings/settings_repository.dart';
import '../../core/theme/glass.dart';
import '../../core/voice/device_voices.dart';
import '../../core/voice/voice_service.dart';

/// Voice Studio (UI-X, Priority 4) — pick the device TTS voice Advary speaks
/// with. Lists the phone's installed voices, previews each, and remembers the
/// chosen one (persisted; re-applied on launch). No native work — pure
/// flutter_tts getVoices/setVoice.
class VoiceStudioScreen extends ConsumerWidget {
  const VoiceStudioScreen({super.key});

  String _companionName(WidgetRef ref) =>
      ref.read(userSettingsProvider).valueOrNull?.companionName?.trim().isNotEmpty == true
          ? ref.read(userSettingsProvider).valueOrNull!.companionName!.trim()
          : 'Advary';

  String _sample(WidgetRef ref) =>
      'Hi, I’m ${_companionName(ref)}. This is how I’ll sound when we talk.';

  Future<void> _preview(WidgetRef ref, DeviceVoice voice) async {
    final engine = ref.read(ttsEngineProvider);
    if (engine is FlutterTtsEngine) await engine.useVoice(voice);
    await ref.read(voiceControllerProvider.notifier).speak(_sample(ref));
  }

  Future<void> _choose(BuildContext context, WidgetRef ref, DeviceVoice voice) async {
    final engine = ref.read(ttsEngineProvider);
    if (engine is FlutterTtsEngine) await engine.useVoice(voice);
    try {
      await ref.read(settingsRepositoryProvider).setSelectedVoice(voice.name, voice.locale);
      ref.invalidate(userSettingsProvider);
      await ref.read(voiceControllerProvider.notifier).speak(_sample(ref));
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('${voice.label} is now my voice')));
      }
    } on AppError catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  Future<void> _useDefault(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(settingsRepositoryProvider).setSelectedVoice(null, null);
      ref.invalidate(userSettingsProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Back to the system default voice (applies on next launch)')));
      }
    } on AppError catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final voices = ref.watch(availableVoicesProvider);
    final selectedName = ref.watch(userSettingsProvider).valueOrNull?.selectedVoice;

    return CompanionScaffold(
      title: 'Voice Studio',
      child: voices.when(
        loading: () => const Center(child: Padding(
          padding: EdgeInsets.all(40), child: CircularProgressIndicator())),
        error: (_, __) => _Empty(onDefault: () => _useDefault(context, ref)),
        data: (list) {
          if (list.isEmpty) return _Empty(onDefault: () => _useDefault(context, ref));
          return ListView(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
            children: [
              _Intro(selected: selectedName != null && selectedName.isNotEmpty,
                  onDefault: () => _useDefault(context, ref)),
              const SizedBox(height: 8),
              for (final v in list)
                _VoiceTile(
                  voice: v,
                  selected: v.name == selectedName,
                  onPreview: () => _preview(ref, v),
                  onChoose: () => _choose(context, ref, v),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _Intro extends StatelessWidget {
  const _Intro({required this.selected, required this.onDefault});
  final bool selected;
  final VoidCallback onDefault;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    return GlassCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const CompanionOrb(state: OrbState.speaking, size: 56),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Choose my voice', style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text('Tap to hear a voice; the check makes it mine. These are the voices installed on your device.',
                    style: tt.bodySmall?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
                if (selected)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      onPressed: onDefault,
                      icon: const Icon(Icons.restart_alt, size: 18),
                      label: const Text('Use device default'),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _VoiceTile extends StatelessWidget {
  const _VoiceTile({
    required this.voice,
    required this.selected,
    required this.onPreview,
    required this.onChoose,
  });
  final DeviceVoice voice;
  final bool selected;
  final VoidCallback onPreview;
  final VoidCallback onChoose;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Card(
      child: ListTile(
        leading: Icon(selected ? Icons.check_circle : Icons.circle_outlined,
            color: selected ? cs.primary : cs.onSurfaceVariant),
        title: Text(voice.label),
        subtitle: voice.locale.isEmpty ? null : Text(voice.locale),
        trailing: IconButton(
          icon: const Icon(Icons.play_arrow),
          tooltip: 'Preview',
          onPressed: onPreview,
        ),
        onTap: onChoose,
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty({required this.onDefault});
  final VoidCallback onDefault;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 24),
      children: [
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const CompanionOrb(state: OrbState.idle, size: 56),
              const SizedBox(height: 12),
              Text('No selectable voices', style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              Text('Your device didn’t report any voices to choose from, so I’ll use the '
                  'system default. You can add more voices in your phone’s '
                  'text-to-speech settings.',
                  style: tt.bodyMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: onDefault,
                  icon: const Icon(Icons.restart_alt, size: 18),
                  label: const Text('Use device default'),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
