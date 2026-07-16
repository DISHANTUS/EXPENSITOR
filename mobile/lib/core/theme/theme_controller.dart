import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'app_theme.dart';

/// Holds the active theme pack, persists the choice on-device, and applies it to
/// [AppColors] so the whole app re-skins at once. Default: Crimson Moon.
const _kThemeKey = 'theme_pack';
const _kMotionKey = 'motion_intensity';
const _storage = FlutterSecureStorage();

void _applySystemChrome(AppPalette p) {
  final iconBrightness = p.brightness == Brightness.dark ? Brightness.light : Brightness.dark;
  SystemChrome.setSystemUIOverlayStyle(SystemUiOverlayStyle(
    statusBarIconBrightness: iconBrightness,
    statusBarBrightness: p.brightness, // iOS reads this one
    systemNavigationBarIconBrightness: iconBrightness,
  ));
}

/// Load the saved pack into [AppColors.active] BEFORE the first frame (no flash).
/// Call from main() before runApp.
Future<void> applySavedTheme() async {
  try {
    final id = await _storage.read(key: _kThemeKey);
    if (id != null) AppColors.active = AppPalettes.byId(id);
  } catch (_) {
    // Keep the default (Crimson Moon) if storage is unavailable.
  }
  _applySystemChrome(AppColors.active);
}

class ThemeController extends StateNotifier<AppPalette> {
  ThemeController() : super(AppColors.active);

  Future<void> select(AppPalette pack) async {
    AppColors.active = pack;       // re-skin everything that reads AppColors
    state = pack;                  // rebuild the MaterialApp theme
    _applySystemChrome(pack);      // keep status bar icons legible under the new brightness
    try {
      await _storage.write(key: _kThemeKey, value: pack.id);
    } catch (_) {/* non-fatal */}
  }
}

/// Watch this in the app root so a theme switch rebuilds the ThemeData.
final themeProvider =
    StateNotifierProvider<ThemeController, AppPalette>((_) => ThemeController());

/// How much ambient "feels alive" motion the user wants — a preference
/// independent of the chosen theme pack. `vitality.dart` widgets read this
/// as a gate/multiplier on top of each palette's `MotionProfile`.
enum MotionIntensity { off, minimal, normal, dynamic }

/// Restored into this before `runApp`, mirroring [applySavedTheme]'s pattern —
/// call `applySavedMotionIntensity()` alongside it in main().
MotionIntensity _savedMotionIntensity = MotionIntensity.normal;

Future<void> applySavedMotionIntensity() async {
  try {
    final v = await _storage.read(key: _kMotionKey);
    if (v != null) {
      _savedMotionIntensity =
          MotionIntensity.values.firstWhere((e) => e.name == v, orElse: () => MotionIntensity.normal);
    }
  } catch (_) {
    // Keep the default (normal) if storage is unavailable.
  }
}

class MotionIntensityController extends StateNotifier<MotionIntensity> {
  MotionIntensityController() : super(_savedMotionIntensity);

  Future<void> select(MotionIntensity value) async {
    state = value;
    try {
      await _storage.write(key: _kMotionKey, value: value.name);
    } catch (_) {/* non-fatal */}
  }
}

final motionIntensityProvider =
    StateNotifierProvider<MotionIntensityController, MotionIntensity>((_) => MotionIntensityController());
