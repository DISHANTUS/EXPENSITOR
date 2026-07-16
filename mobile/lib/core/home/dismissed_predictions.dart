import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Remembers which predicted habits the user said "No" to today, so a
/// declined card doesn't bounce straight back on the next refetch. Local and
/// day-scoped on purpose: "not today" is not a lasting fact about the user,
/// so it never reaches the backend or the learning loop.
class DismissedPredictions extends StateNotifier<Set<String>> {
  DismissedPredictions([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage(),
        super(<String>{}) {
    _load();
  }

  final FlutterSecureStorage _storage;
  static const _key = 'dismissed_predictions';

  static String _todayKey() {
    final n = DateTime.now();
    return '${n.year.toString().padLeft(4, '0')}-${n.month.toString().padLeft(2, '0')}-${n.day.toString().padLeft(2, '0')}';
  }

  Future<void> _load() async {
    final raw = await _storage.read(key: _key);
    if (raw == null || raw.isEmpty) return;
    final parts = raw.split('|');
    // Stored as "<date>|<id>|<id>…" — a different date means yesterday's
    // dismissals expire on their own, no cleanup job needed.
    if (parts.isEmpty || parts.first != _todayKey()) return;
    state = parts.skip(1).where((s) => s.isNotEmpty).toSet();
  }

  Future<void> dismiss(String categoryId) async {
    state = {...state, categoryId};
    await _storage.write(key: _key, value: '${_todayKey()}|${state.join('|')}');
  }
}

final dismissedPredictionsProvider =
    StateNotifierProvider<DismissedPredictions, Set<String>>((ref) => DismissedPredictions());
