import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Which fact categories the user has switched OFF. Stored on-device (facts are
/// non-sensitive); an empty set means "all categories on". We persist the *off*
/// set so newly added packs are enabled by default.
class FactsPrefs {
  FactsPrefs(this._storage);
  final FlutterSecureStorage _storage;
  static const _key = 'facts_disabled_categories';

  Future<Set<String>> disabled() async {
    final raw = await _storage.read(key: _key);
    if (raw == null || raw.isEmpty) return <String>{};
    return raw.split(',').map((s) => s.trim()).where((s) => s.isNotEmpty).toSet();
  }

  Future<void> setDisabled(Set<String> keys) =>
      _storage.write(key: _key, value: keys.join(','));

  Future<void> toggle(String key, {required bool enabled}) async {
    final off = await disabled();
    if (enabled) {
      off.remove(key);
    } else {
      off.add(key);
    }
    await setDisabled(off);
  }
}

final factsPrefsProvider = Provider<FactsPrefs>((_) => FactsPrefs(const FlutterSecureStorage()));

/// The set of disabled category keys, exposed for the UI (Settings toggles +
/// filtering which categories facts are drawn from).
final disabledFactCategoriesProvider = FutureProvider<Set<String>>(
    (ref) => ref.watch(factsPrefsProvider).disabled());
