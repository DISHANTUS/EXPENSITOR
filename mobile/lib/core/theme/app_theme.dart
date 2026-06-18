import 'package:animations/animations.dart';
import 'package:flutter/material.dart';

/// A theme pack's colour set. The ENTIRE app look — orb, aurora, glass, glow rail,
/// calendar markers, celebrations, buttons, progress bars — is derived from these,
/// so switching the active palette re-skins everything at once. (Sprint Theme Studio)
class AppPalette {
  const AppPalette({
    required this.id,
    required this.name,
    required this.emoji,
    required this.bg,
    required this.surface,
    required this.surfaceHi,
    required this.primary,
    required this.secondary,
    required this.accent,
    required this.spark,
    required this.on,
    required this.muted,
    this.error = const Color(0xFFFF6B7A),
  });

  final String id;        // crimson | aurora | midnight | sakura
  final String name;      // "Crimson Moon"
  final String emoji;     // 🩸
  final Color bg;         // near-black base
  final Color surface;    // card / graphite
  final Color surfaceHi;  // elevated surface
  final Color primary;    // identity colour (idle orb, buttons, glow rail)
  final Color secondary;  // highlight (speaking/listening rings, secondary accents)
  final Color accent;     // pop (relationship hero, accents)
  final Color spark;      // celebration sparks (the "+ gold" pop)
  final Color on;         // text on dark
  final Color muted;      // secondary text
  final Color error;

  List<Color> get aurora => [primary, secondary, accent];
}

/// The four shipped theme packs.
class AppPalettes {
  const AppPalettes._();

  static const crimson = AppPalette(
    id: 'crimson', name: 'Crimson Moon', emoji: '🩸',
    bg: Color(0xFF0A0608), surface: Color(0xFF161014), surfaceHi: Color(0xFF221820),
    primary: Color(0xFFC81E3A),      // crimson
    secondary: Color(0xFFC9CED6),    // moon silver
    accent: Color(0xFFFF3B5C),       // scarlet
    spark: Color(0xFFFFC247),        // gold (celebration)
    on: Color(0xFFF4E9EC), muted: Color(0xFFAB8E97),
  );

  static const aurora = AppPalette(
    id: 'aurora', name: 'Aurora', emoji: '🌌',
    bg: Color(0xFF0B1020), surface: Color(0xFF141B2D), surfaceHi: Color(0xFF1B2540),
    primary: Color(0xFF7C5CFF),      // violet
    secondary: Color(0xFF00D4FF),    // cyan
    accent: Color(0xFFFF5FBF),       // pink
    spark: Color(0xFF00D4FF),
    on: Color(0xFFEAF0FF), muted: Color(0xFF9AA6C7),
  );

  static const midnight = AppPalette(
    id: 'midnight', name: 'Midnight Blue', emoji: '🌃',
    bg: Color(0xFF070B16), surface: Color(0xFF0F1626), surfaceHi: Color(0xFF16203A),
    primary: Color(0xFF2E6BFF),      // deep blue
    secondary: Color(0xFF5FE0FF),    // ice blue
    accent: Color(0xFF8AB4FF),
    spark: Color(0xFF9EE7FF),
    on: Color(0xFFE6EEFF), muted: Color(0xFF8896B5),
  );

  static const sakura = AppPalette(
    id: 'sakura', name: 'Sakura Dream', emoji: '🌸',
    bg: Color(0xFF140E14), surface: Color(0xFF1E1620), surfaceHi: Color(0xFF281C2C),
    primary: Color(0xFFFF8FB3),      // sakura pink
    secondary: Color(0xFFC9A7FF),    // lavender
    accent: Color(0xFFFFD1E0),       // blossom
    spark: Color(0xFFFFE08A),        // soft gold
    on: Color(0xFFFBEFF4), muted: Color(0xFFB79CAE),
  );

  static const all = [crimson, aurora, midnight, sakura];

  static AppPalette byId(String? id) =>
      all.firstWhere((p) => p.id == id, orElse: () => crimson);
}

/// Aurora design language (Sprint UI-X), now palette-driven (Theme Studio).
/// All members read the runtime [active] palette so a theme switch re-skins the
/// whole app. Default is Crimson Moon; the chosen pack is restored on launch.
class AppColors {
  const AppColors._();

  static AppPalette active = AppPalettes.crimson;

  static Color get bg => active.bg;
  static Color get surface => active.surface;
  static Color get surfaceHi => active.surfaceHi;
  static Color get primary => active.primary;
  static Color get secondary => active.secondary;
  static Color get accent => active.accent;
  static Color get spark => active.spark;
  static Color get on => active.on;
  static Color get muted => active.muted;

  static List<Color> get aurora => active.aurora;
  static LinearGradient get gradient => LinearGradient(
      colors: [active.primary, active.secondary], begin: Alignment.centerLeft, end: Alignment.centerRight);
  static LinearGradient get gradientFull => LinearGradient(
      colors: [active.primary, active.secondary, active.accent], begin: Alignment.topLeft, end: Alignment.bottomRight);

  /// A muted, darkened variant of a colour — the companion's "concerned" tone
  /// (dark red for Crimson, muted violet for Aurora, etc.).
  static Color concernedOf(Color c) {
    final h = HSLColor.fromColor(c);
    return h.withSaturation((h.saturation * 0.55).clamp(0.0, 1.0))
        .withLightness((h.lightness * 0.6).clamp(0.0, 1.0)).toColor();
  }

  static Color get concerned => concernedOf(active.primary);
}

class AppTheme {
  const AppTheme._();

  /// Build the dark ThemeData for the currently-active palette. Called whenever
  /// the theme changes so Material widgets (buttons, chips, inputs) re-skin too.
  static ThemeData dark() {
    final p = AppColors.active;
    // Containers + outlines derived from the palette so every pack is coherent.
    Color container(Color c) => Color.alphaBlend(c.withValues(alpha: 0.28), p.surface);
    final outline = Color.alphaBlend(p.muted.withValues(alpha: 0.45), p.bg);
    final outlineVariant = Color.alphaBlend(p.muted.withValues(alpha: 0.22), p.bg);

    final scheme = ColorScheme.dark(
      brightness: Brightness.dark,
      primary: p.primary,
      onPrimary: Colors.white,
      primaryContainer: container(p.primary),
      onPrimaryContainer: p.on,
      secondary: p.secondary,
      onSecondary: const Color(0xFF101418),
      secondaryContainer: container(p.secondary),
      onSecondaryContainer: p.on,
      tertiary: p.accent,
      onTertiary: const Color(0xFF1A0B12),
      tertiaryContainer: container(p.accent),
      onTertiaryContainer: p.on,
      surface: p.surface,
      onSurface: p.on,
      surfaceContainerHighest: p.surfaceHi,
      onSurfaceVariant: p.muted,
      outline: outline,
      outlineVariant: outlineVariant,
      error: p.error,
    );

    final base = ThemeData(colorScheme: scheme, useMaterial3: true, scaffoldBackgroundColor: p.bg);
    return base.copyWith(
      textTheme: _typography(base.textTheme, p),
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent, elevation: 0, scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(color: p.on, fontSize: 20, fontWeight: FontWeight.w700),
        iconTheme: IconThemeData(color: p.on),
      ),
      cardTheme: CardThemeData(
        color: p.surface, elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        margin: const EdgeInsets.symmetric(vertical: 6),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(50), foregroundColor: Colors.white,
          backgroundColor: p.primary, textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: Colors.white.withValues(alpha: 0.06),
        selectedColor: p.primary,
        side: BorderSide(color: Colors.white.withValues(alpha: 0.12)),
        labelStyle: TextStyle(color: p.on, fontWeight: FontWeight.w600),
        secondaryLabelStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true, fillColor: Colors.white.withValues(alpha: 0.05),
        hintStyle: TextStyle(color: p.muted),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.12))),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.12))),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: p.primary, width: 1.5)),
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(color: p.primary),
      dividerTheme: DividerThemeData(color: outlineVariant),
      pageTransitionsTheme: const PageTransitionsTheme(builders: {
        TargetPlatform.android: FadeThroughPageTransitionsBuilder(),
        TargetPlatform.iOS: FadeThroughPageTransitionsBuilder(),
      }),
    );
  }

  static TextTheme _typography(TextTheme t, AppPalette p) => t.copyWith(
        headlineLarge: t.headlineLarge?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.5, color: p.on),
        headlineMedium: t.headlineMedium?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.5, color: p.on),
        titleLarge: t.titleLarge?.copyWith(fontWeight: FontWeight.w700, color: p.on),
        titleMedium: t.titleMedium?.copyWith(fontWeight: FontWeight.w700, color: p.on),
        bodyMedium: t.bodyMedium?.copyWith(color: p.on, height: 1.4),
        bodySmall: t.bodySmall?.copyWith(color: p.muted, height: 1.35),
        labelLarge: t.labelLarge?.copyWith(fontWeight: FontWeight.w700),
      );
}
