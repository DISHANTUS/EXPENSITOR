import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/settings/settings_repository.dart';
import '../budget_setup/festival_repository.dart';

/// Whose festivals Advary should track.
///
/// This is the question GPS cannot answer. Location tells you where someone
/// IS; this asks who they ARE. An Indian student in Tokyo wants Diwali *and*
/// Golden Week, and a location-driven app would quietly take Diwali away the
/// moment they landed. So: ask once, allow more than one, and let it override
/// everything the app guessed.
///
/// Left alone, it stays empty and the app works it out from the phone's
/// timezone, then the base currency — no prompt, nothing to configure.
const _regionLabels = <String, String>{
  'IN': 'India',
  'JP': 'Japan',
};

class FestivalRegionsTile extends ConsumerStatefulWidget {
  const FestivalRegionsTile({super.key});

  @override
  ConsumerState<FestivalRegionsTile> createState() => _FestivalRegionsTileState();
}

class _FestivalRegionsTileState extends ConsumerState<FestivalRegionsTile> {
  bool _saving = false;

  Future<void> _toggle(Set<String> current, String region) async {
    final next = Set<String>.from(current);
    next.contains(region) ? next.remove(region) : next.add(region);

    final messenger = ScaffoldMessenger.of(context);
    setState(() => _saving = true);
    try {
      await ref.read(settingsRepositoryProvider).setFestivalRegions(next.toList()..sort());
      if (!mounted) return;
      setState(() => _saving = false);
      ref.invalidate(userSettingsProvider);
      // The card reads from the server; it must re-ask or it'll keep showing
      // the old region's festivals.
      ref.invalidate(festivalsProvider);
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      messenger.showSnackBar(SnackBar(
        content: Text(e is AppError ? e.message : "Couldn't save that just now"),
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final prefs = ref.watch(userSettingsProvider).valueOrNull?.notificationPreferences ?? const {};
    final chosen = {
      for (final r in (prefs['festival_regions'] as List? ?? const [])) r.toString(),
    };

    return Card(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            leading: const Icon(Icons.celebration_outlined),
            title: const Text('Festivals to track'),
            subtitle: Text(
              chosen.isEmpty
                  // Honest about the fallback rather than pretending nothing is set.
                  ? 'Working it out from your timezone and currency. Tap to choose.'
                  : chosen.map((r) => _regionLabels[r] ?? r).join(' + '),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: Wrap(
              spacing: 8,
              children: [
                for (final entry in _regionLabels.entries)
                  FilterChip(
                    label: Text(entry.value),
                    selected: chosen.contains(entry.key),
                    onSelected: _saving ? null : (_) => _toggle(chosen, entry.key),
                  ),
              ],
            ),
          ),
          if (chosen.length > 1)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: Text(
                "I'll track both, in date order — moving somewhere doesn't mean the "
                'festivals you grew up with stop being yours.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
        ],
      ),
    );
  }
}
