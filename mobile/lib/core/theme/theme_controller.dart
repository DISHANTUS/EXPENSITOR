import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'app_theme.dart';

/// Holds the active theme pack, persists the choice on-device, and applies it to
/// [AppColors] so the whole app re-skins at once. Default: Crimson Moon.
const _kThemeKey = 'theme_pack';
const _storage = FlutterSecureStorage();

/// Load the saved pack into [AppColors.active] BEFORE the first frame (no flash).
/// Call from main() before runApp.
Future<void> applySavedTheme() async {
  try {
    final id = await _storage.read(key: _kThemeKey);
    if (id != null) AppColors.active = AppPalettes.byId(id);
  } catch (_) {
    // Keep the default (Crimson Moon) if storage is unavailable.
  }
}

class ThemeController extends StateNotifier<AppPalette> {
  ThemeController() : super(AppColors.active);

  Future<void> select(AppPalette pack) async {
    AppColors.active = pack;       // re-skin everything that reads AppColors
    state = pack;                  // rebuild the MaterialApp theme
    try {
      await _storage.write(key: _kThemeKey, value: pack.id);
    } catch (_) {/* non-fatal */}
  }
}

/// Watch this in the app root so a theme switch rebuilds the ThemeData.
final themeProvider =
    StateNotifierProvider<ThemeController, AppPalette>((_) => ThemeController());
