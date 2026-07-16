import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Which Home body to show: [full] is the planning-first calendar view,
/// [compact] is the "safe to spend today" quick-check view. First app open of
/// a calendar day shows [full]; every open after that, same day, shows
/// [compact] — until the device-local date rolls over.
enum HomeViewMode { full, compact }

class HomeDayStateController extends StateNotifier<HomeViewMode> {
  HomeDayStateController([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage(),
        super(HomeViewMode.full) {
    _init();
  }

  final FlutterSecureStorage _storage;
  static const _key = 'home_last_full_open_date';

  String _todayKey() {
    final now = DateTime.now();
    final y = now.year.toString().padLeft(4, '0');
    final m = now.month.toString().padLeft(2, '0');
    final d = now.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  Future<void> _init() async {
    final today = _todayKey();
    final last = await _storage.read(key: _key);
    if (last == today) {
      state = HomeViewMode.compact;
    } else {
      state = HomeViewMode.full;
      await _storage.write(key: _key, value: today);
    }
  }

  /// An explicit ask to see the calendar (drawer → Home) — doesn't reset the
  /// "already showed the full view today" flag, so the smart default still
  /// applies to the next cold start.
  void forceFull() => state = HomeViewMode.full;
}

final homeDayStateProvider = StateNotifierProvider<HomeDayStateController, HomeViewMode>(
    (ref) => HomeDayStateController());
