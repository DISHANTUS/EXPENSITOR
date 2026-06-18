import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/auth/auth_controller.dart';
import '../../core/companion/mood_repository.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/future_me/future_me_repository.dart';
import '../../core/onboarding/tour_controller.dart';
import '../../core/relationships/relationship_repository.dart';
import '../../core/settings/settings_repository.dart';
import '../../core/timeline/timeline_repository.dart';
import '../../core/voice/voice_service.dart';
import '../calendar/calendar_repository.dart';
import '../home/dashboard_repository.dart';

const _companionStyles = ['balanced', 'cheerful', 'professional', 'anime', 'minimal'];
const _voiceLengths = ['short', 'normal', 'detailed'];

Future<void> changeVoiceLength(BuildContext context, WidgetRef ref) async {
  final picked = await showDialog<String>(
    context: context,
    builder: (c) => SimpleDialog(
      title: const Text('Voice length'),
      children: [
        for (final v in _voiceLengths)
          SimpleDialogOption(onPressed: () => Navigator.pop(c, v), child: Text(v[0].toUpperCase() + v.substring(1))),
      ],
    ),
  );
  if (picked == null) return;
  try {
    await ref.read(settingsRepositoryProvider).setVoiceLength(picked);
    ref.invalidate(userSettingsProvider);
    ref.invalidate(companionMoodProvider);   // spoken_text length changes
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Voice length: $picked')));
    }
  } on AppError catch (e) {
    if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
  }
}

Future<void> changeCompanionStyle(BuildContext context, WidgetRef ref) async {
  final picked = await showDialog<String>(
    context: context,
    builder: (c) => SimpleDialog(
      title: const Text('Companion style'),
      children: [
        for (final s in _companionStyles)
          SimpleDialogOption(onPressed: () => Navigator.pop(c, s), child: Text(s[0].toUpperCase() + s.substring(1))),
      ],
    ),
  );
  if (picked == null) return;
  try {
    await ref.read(settingsRepositoryProvider).setCompanionStyle(picked);
    ref.invalidate(userSettingsProvider);
    ref.invalidate(companionMoodProvider);   // re-greet in the new voice
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Companion style: $picked')));
    }
  } on AppError catch (e) {
    if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
  }
}

const _companionNames = ['Advary', 'Hikari', 'Auri', 'Sora', 'Nova'];

/// Reset / Clean-Slate (pre-Sprint-8): irreversible confirmation, then wipe/seed
/// and refresh every companion surface so the fresh state shows immediately.
Future<void> resetCompanionData(BuildContext context, WidgetRef ref,
    {required String mode, required String title, required String body, required String confirmLabel}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (c) => AlertDialog(
      title: Text(title),
      content: Text('$body\n\nThis can’t be undone.'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
        FilledButton(
          style: mode == 'demo' ? null : FilledButton.styleFrom(backgroundColor: Theme.of(c).colorScheme.error),
          onPressed: () => Navigator.pop(c, true),
          child: Text(confirmLabel),
        ),
      ],
    ),
  );
  if (ok != true) return;
  try {
    await ref.read(settingsRepositoryProvider).reset(mode);
    for (final p in [companionMoodProvider, timelineProvider, futureMeProvider,
                     relationshipsProvider, userSettingsProvider, monthViewProvider, dailyBriefProvider]) {
      ref.invalidate(p);
    }
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(mode == 'demo' ? 'Demo data loaded.' : 'Reset complete — Advary is starting fresh.')));
      context.go('/home');
    }
  } on AppError catch (e) {
    if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
  }
}

/// Name the companion (6c): pick a suggestion, type a custom name, or clear it.
Future<void> changeCompanionName(BuildContext context, WidgetRef ref, String? current) async {
  final ctrl = TextEditingController(text: current ?? '');
  final picked = await showDialog<String>(
    context: context,
    builder: (c) => AlertDialog(
      title: const Text('Companion name'),
      content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Wrap(spacing: 8, children: [
          for (final n in _companionNames)
            ActionChip(label: Text(n), onPressed: () => Navigator.pop(c, n)),
        ]),
        const SizedBox(height: 12),
        TextField(controller: ctrl, decoration: const InputDecoration(labelText: 'Or type a name')),
      ]),
      actions: [
        TextButton(onPressed: () => Navigator.pop(c, ''), child: const Text('Clear')),
        TextButton(onPressed: () => Navigator.pop(c, null), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(c, ctrl.text.trim()), child: const Text('Save')),
      ],
    ),
  );
  if (picked == null) return;   // cancelled
  try {
    await ref.read(settingsRepositoryProvider).setCompanionName(picked);
    ref.invalidate(userSettingsProvider);
    ref.invalidate(companionMoodProvider);   // greeting sign-off + drawer refresh
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(picked.isEmpty ? 'Companion name cleared' : 'Companion named $picked')));
    }
  } on AppError catch (e) {
    if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
  }
}

/// Lets the user change anything that uses their preferred currency everywhere.
Future<void> changePreferredCurrency(BuildContext context, WidgetRef ref) async {
  final codes = await ref.read(currenciesProvider.future).catchError((_) => <String>['INR', 'USD', 'EUR', 'GBP', 'JPY']);
  if (!context.mounted) return;
  final picked = await showDialog<String>(
    context: context,
    builder: (c) => SimpleDialog(
      title: const Text('Preferred currency'),
      children: [for (final code in codes) SimpleDialogOption(onPressed: () => Navigator.pop(c, code), child: Text(code))],
    ),
  );
  if (picked == null) return;
  try {
    await ref.read(settingsRepositoryProvider).setBaseCurrency(picked);
    ref.invalidate(userSettingsProvider);
    ref.invalidate(monthViewProvider);
    ref.invalidate(dailyBriefProvider);
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Currency set to $picked')));
    }
  } on AppError catch (e) {
    if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
  }
}

/// The four voice toggles (4c-B polish). Spoken text (greeting.spoken_text) is
/// ready for Sprint 5 TTS; these settings decide what gets read aloud.
class _VoiceToggles extends ConsumerWidget {
  const _VoiceToggles({required this.prefs});
  final Map<String, bool> prefs;

  static const _items = [
    ('speak_greeting_on_open', 'Read greeting on app open'),
    ('speak_reminders', 'Read important reminders'),
    ('speak_celebrations', 'Read celebrations'),
    ('voice_when_tapped_only', 'Voice only when tapped'),
  ];

  Future<void> _toggle(BuildContext context, WidgetRef ref, String key, bool value) async {
    final next = Map<String, bool>.from(prefs)..[key] = value;
    try {
      await ref.read(settingsRepositoryProvider).setNotificationPreferences(next);
      ref.invalidate(userSettingsProvider);
    } on AppError catch (e) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: Column(
        children: [
          for (final (key, label) in _items)
            SwitchListTile(
              title: Text(label),
              value: prefs[key] ?? false,
              onChanged: (v) => _toggle(context, ref, key, v),
            ),
        ],
      ),
    );
  }
}

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(userSettingsProvider);
    final isDev = ref.watch(authControllerProvider).user?.isDeveloper ?? false;
    return CompanionScaffold(
      title: 'Settings',
      commentary: 'Set the currency you think in — I’ll use it everywhere.',
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.payments_outlined),
              title: const Text('Preferred currency'),
              subtitle: const Text('Used for budgets, reports and advice'),
              trailing: Text(settings.valueOrNull?.baseCurrency ?? '—',
                  style: Theme.of(context).textTheme.titleMedium),
              onTap: () => changePreferredCurrency(context, ref),
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.face_retouching_natural_outlined),
              title: const Text('Companion style'),
              subtitle: const Text('Same facts — different personality'),
              trailing: Text(settings.valueOrNull?.companionStyle ?? 'balanced',
                  style: Theme.of(context).textTheme.titleMedium),
              onTap: () => changeCompanionStyle(context, ref),
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.badge_outlined),
              title: const Text('Companion name'),
              subtitle: const Text('Give your companion a name'),
              trailing: Text(settings.valueOrNull?.companionName ?? 'Advary',
                  style: Theme.of(context).textTheme.titleMedium),
              onTap: () => changeCompanionName(context, ref, settings.valueOrNull?.companionName),
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.record_voice_over_outlined),
              title: const Text('Advisor tone'),
              trailing: Text(settings.valueOrNull?.aiTone ?? '—'),
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.tips_and_updates_outlined),
              title: const Text('Take the tour again'),
              subtitle: const Text('Let me show you around the app'),
              trailing: const Icon(Icons.play_circle_outline),
              onTap: () => ref.read(tourControllerProvider.notifier).start(),
            ),
          ),
          const SizedBox(height: 8),
          const Padding(
            padding: EdgeInsets.fromLTRB(4, 4, 4, 4),
            child: Text('Voice Companion', style: TextStyle(fontWeight: FontWeight.w600)),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.speed_outlined),
              title: const Text('Voice length'),
              subtitle: const Text('How much the companion reads aloud'),
              trailing: Text(settings.valueOrNull?.voiceLength ?? 'normal',
                  style: Theme.of(context).textTheme.titleMedium),
              onTap: () => changeVoiceLength(context, ref),
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.volume_up_outlined),
              title: const Text('Test voice'),
              subtitle: const Text('Hear how the companion sounds'),
              trailing: const Icon(Icons.play_arrow),
              onTap: () => ref.read(voiceControllerProvider.notifier)
                  .speak('Hi, I’m your Expensitor companion. This is how I sound.'),
            ),
          ),
          _VoiceToggles(prefs: settings.valueOrNull?.notificationPreferences ?? const {}),
          // Developer-only tools — hidden for normal users (the API also 403s them).
          if (isDev) ...[
            const SizedBox(height: 8),
            const Padding(
              padding: EdgeInsets.fromLTRB(4, 4, 4, 4),
              child: Text('Developer / Testing', style: TextStyle(fontWeight: FontWeight.w600)),
            ),
            Card(
              child: ListTile(
                leading: const Icon(Icons.auto_awesome_outlined),
                title: const Text('Load demo data'),
                subtitle: const Text('Replace with a fictional sample so a friend can explore'),
                onTap: () => resetCompanionData(context, ref, mode: 'demo',
                    title: 'Load demo data?', body: 'This replaces your data with a fictional sample.',
                    confirmLabel: 'Load demo'),
              ),
            ),
            Card(
              child: ListTile(
                leading: const Icon(Icons.cleaning_services_outlined),
                title: const Text('Reset companion data'),
                subtitle: const Text('Clear your story — keep your account & settings'),
                onTap: () => resetCompanionData(context, ref, mode: 'soft',
                    title: 'Reset companion data?',
                    body: 'Deletes your timeline, memories, goals, people, lessons and history.',
                    confirmLabel: 'Reset'),
              ),
            ),
            Card(
              child: ListTile(
                leading: Icon(Icons.delete_forever_outlined, color: Theme.of(context).colorScheme.error),
                title: const Text('Full reset'),
                subtitle: const Text('Everything except your account'),
                onTap: () => resetCompanionData(context, ref, mode: 'full',
                    title: 'Full reset?', body: 'Deletes all data and resets settings to defaults.',
                    confirmLabel: 'Erase all'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
