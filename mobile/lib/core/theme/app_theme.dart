import 'package:animations/animations.dart';
import 'package:flutter/material.dart';

/// How a palette's background is painted. `flat`/`scan` exist because most of
/// the newer theme packs deliberately move away from the glowing-aurora look.
enum BackgroundStyle { aurora, flat, scan }

/// How [GlassCard] (and anything else that reads it) renders a surface for
/// this palette — the frosted-glass look is one option among several now,
/// not the only one.
enum SurfaceStyle { glass, flatOutlined, neomorphic, paperRuled, panelBorder }

/// Display typeface per palette. Deliberately maps to Flutter's built-in
/// generic font families (no bundled font assets, no new dependency) — the
/// same pragmatic "system font stack" already used across the web prototypes
/// this palette set was designed from.
enum DisplayFont { defaultSans, serif, mono }

/// How much a palette's ambient motion moves — one shared multiplier table
/// instead of every theme hand-tuning its own animation durations/amplitudes.
enum ThemeEnergy { veryLow, low, medium, high, veryHigh }

/// A coarse "voice" label a palette carries. Companion text formatting reads
/// this (not 19 individual theme ids) so a future theme inherits sensible
/// phrasing just by picking a personality — see `themeVoice()` (Phase 4).
enum ThemePersonality { playful, elegant, futuristic, nostalgic, energetic, minimal }

/// Which ambient "feels alive" behaviours a palette opts into. Consumed by
/// the `vitality.dart` toolkit. All false = today's static behaviour.
class MotionProfile {
  const MotionProfile({
    this.idleWobble = false,
    this.breathingGlow = false,
    this.movingStripes = false,
    this.blinkingCursor = false,
    this.tickerText = false,
  });

  final bool idleWobble;
  final bool breathingGlow;
  final bool movingStripes;
  final bool blinkingCursor;
  final bool tickerText;

  static const calm = MotionProfile();
}

/// A theme pack's colour set (+ typography/background/surface/motion). The
/// ENTIRE app look — orb, aurora, glass, glow rail, calendar markers,
/// celebrations, buttons, progress bars — is derived from these, so
/// switching the active palette re-skins everything at once. (Sprint Theme
/// Studio, extended for the 15-pack "feels alive" rollout.)
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
    this.background = BackgroundStyle.aurora,
    this.surfaceStyle = SurfaceStyle.glass,
    this.displayFont = DisplayFont.defaultSans,
    this.energy = ThemeEnergy.medium,
    this.personality = ThemePersonality.elegant,
    this.brightness = Brightness.dark,
    this.onPrimaryOverride,
    this.motion = MotionProfile.calm,
  });

  final String id;        // crimson | aurora | midnight | sakura | ...
  final String name;      // "Crimson Moon"
  final String emoji;     // 🩸
  final Color bg;         // page background
  final Color surface;    // card / graphite
  final Color surfaceHi;  // elevated surface
  final Color primary;    // identity colour (idle orb, buttons, glow rail)
  final Color secondary;  // highlight (speaking/listening rings, secondary accents)
  final Color accent;     // pop (relationship hero, accents)
  final Color spark;      // celebration sparks (the "+ gold" pop)
  final Color on;         // text on the page background
  final Color muted;      // secondary text
  final Color error;

  final BackgroundStyle background;
  final SurfaceStyle surfaceStyle;
  final DisplayFont displayFont;
  final ThemeEnergy energy;
  final ThemePersonality personality;

  /// Every existing pack is dark. Most of the 15 new ones are light — this
  /// drives `AppTheme`'s ColorScheme branch, the status bar style, and
  /// `AppColors.hairline`.
  final Brightness brightness;

  /// Overrides the fixed `Colors.white` button-text colour — only needed for
  /// palettes whose `primary` is bright/pastel enough that white fails
  /// contrast (e.g. a mint or phosphor-green primary).
  final Color? onPrimaryOverride;

  /// Which ambient "feels alive" behaviours this pack opts into (moving
  /// stripes, a blinking cursor, ...). Consumed by `vitality.dart`.
  final MotionProfile motion;

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

  // --- The 15 packs designed across the "feels alive" prototype rounds. ---

  static const philately = AppPalette(
    id: 'philately', name: 'Philately', emoji: '✉️',
    bg: Color(0xFFF3ECDD), surface: Color(0xFFFBF7ED), surfaceHi: Color(0xFFF5EEDD),
    primary: Color(0xFFC23B32), secondary: Color(0xFF2F5C8A), accent: Color(0xFFC23B32),
    spark: Color(0xFFD9A441), on: Color(0xFF25324A), muted: Color(0xFF8A8570),
    background: BackgroundStyle.flat, surfaceStyle: SurfaceStyle.flatOutlined,
    displayFont: DisplayFont.serif, energy: ThemeEnergy.low, personality: ThemePersonality.nostalgic,
    brightness: Brightness.light, motion: MotionProfile(breathingGlow: true),
  );

  static const collage = AppPalette(
    id: 'collage', name: 'Collage', emoji: '✂️',
    bg: Color(0xFFDCC9A3), surface: Color(0xFFF6EEDD), surfaceHi: Color(0xFFFBF6EA),
    primary: Color(0xFFC24B3E), secondary: Color(0xFF4E6E4A), accent: Color(0xFFC24B3E),
    spark: Color(0xFFD9A441), on: Color(0xFF33281B), muted: Color(0xFF7A6C52),
    background: BackgroundStyle.flat, surfaceStyle: SurfaceStyle.flatOutlined,
    displayFont: DisplayFont.serif, energy: ThemeEnergy.medium, personality: ThemePersonality.nostalgic,
    brightness: Brightness.light, motion: MotionProfile(idleWobble: true),
  );

  static const cyberpunk = AppPalette(
    id: 'cyberpunk', name: 'Cyberpunk', emoji: '🖥️',
    bg: Color(0xFF07090C), surface: Color(0xFF0F1620), surfaceHi: Color(0xFF152030),
    primary: Color(0xFF00E5C7), secondary: Color(0xFF00B8A0), accent: Color(0xFF00E5C7),
    spark: Color(0xFFD9FBFF), on: Color(0xFFD9FBFF), muted: Color(0xFF5C7A85),
    background: BackgroundStyle.scan, surfaceStyle: SurfaceStyle.panelBorder,
    displayFont: DisplayFont.mono, energy: ThemeEnergy.medium, personality: ThemePersonality.futuristic,
    onPrimaryOverride: Color(0xFF07090C), motion: MotionProfile(breathingGlow: true),
  );

  static const nihon = AppPalette(
    id: 'nihon', name: 'Nihon', emoji: '🎏',
    bg: Color(0xFFF7F5EF), surface: Color(0xFFFFFFFF), surfaceHi: Color(0xFFF2EFE6),
    primary: Color(0xFFB5342B), secondary: Color(0xFF5B6B58), accent: Color(0xFFB5342B),
    spark: Color(0xFFC9A15A), on: Color(0xFF191714), muted: Color(0xFF9C968A),
    background: BackgroundStyle.flat, surfaceStyle: SurfaceStyle.flatOutlined,
    energy: ThemeEnergy.veryLow, personality: ThemePersonality.elegant,
    brightness: Brightness.light,
  );

  static const terminal = AppPalette(
    id: 'terminal', name: 'Terminal', emoji: '💻',
    bg: Color(0xFF050705), surface: Color(0xFF0B120C), surfaceHi: Color(0xFF122016),
    primary: Color(0xFF39FF6A), secondary: Color(0xFF39FF6A), accent: Color(0xFF39FF6A),
    spark: Color(0xFF39FF6A), on: Color(0xFF39FF6A), muted: Color(0xFF1F7A3E),
    background: BackgroundStyle.scan, surfaceStyle: SurfaceStyle.panelBorder,
    displayFont: DisplayFont.mono, energy: ThemeEnergy.low, personality: ThemePersonality.futuristic,
    onPrimaryOverride: Color(0xFF07110D), motion: MotionProfile(blinkingCursor: true, tickerText: true),
  );

  static const quest = AppPalette(
    id: 'quest', name: 'Quest', emoji: '🎮',
    bg: Color(0xFF0B0D12), surface: Color(0xFF141821), surfaceHi: Color(0xFF1B212E),
    primary: Color(0xFF33E39A), secondary: Color(0xFF33E39A), accent: Color(0xFF33E39A),
    spark: Color(0xFF33E39A), on: Color(0xFFEAF3EE), muted: Color(0xFF6E7A8C),
    surfaceStyle: SurfaceStyle.flatOutlined,
    displayFont: DisplayFont.mono, energy: ThemeEnergy.high, personality: ThemePersonality.energetic,
    onPrimaryOverride: Color(0xFF08110D), motion: MotionProfile(breathingGlow: true),
  );

  static const tactile = AppPalette(
    id: 'tactile', name: 'Tactile', emoji: '🎛️',
    bg: Color(0xFFE3E3E3), surface: Color(0xFFE3E3E3), surfaceHi: Color(0xFFEAEAEA),
    primary: Color(0xFFD42B2B), secondary: Color(0xFF3B3B40), accent: Color(0xFFD42B2B),
    spark: Color(0xFFD42B2B), on: Color(0xFF26262A), muted: Color(0xFF84848A),
    background: BackgroundStyle.flat, surfaceStyle: SurfaceStyle.neomorphic,
    displayFont: DisplayFont.mono, energy: ThemeEnergy.low, personality: ThemePersonality.minimal,
    brightness: Brightness.light,
  );

  static const clay = AppPalette(
    id: 'clay', name: 'Clay', emoji: '🧸',
    bg: Color(0xFFEAE3F6), surface: Color(0xFFF5F1FC), surfaceHi: Color(0xFFEFE9FA),
    primary: Color(0xFFFF9FC6), secondary: Color(0xFF7ED0A8), accent: Color(0xFFFF9FC6),
    spark: Color(0xFFFFD9A0), on: Color(0xFF332C4D), muted: Color(0xFF8B80AD),
    background: BackgroundStyle.flat, surfaceStyle: SurfaceStyle.neomorphic,
    energy: ThemeEnergy.high, personality: ThemePersonality.playful,
    brightness: Brightness.light, onPrimaryOverride: Color(0xFF3A2A3D),
    motion: MotionProfile(idleWobble: true, breathingGlow: true),
  );

  static const ledger = AppPalette(
    id: 'ledger', name: 'Ledger', emoji: '📒',
    bg: Color(0xFFD9E3D1), surface: Color(0xFFE6EEDF), surfaceHi: Color(0xFFDEE8D5),
    primary: Color(0xFF8B2E22), secondary: Color(0xFF2E4B6B), accent: Color(0xFF8B2E22),
    spark: Color(0xFFA67C3D), on: Color(0xFF2B2419), muted: Color(0xFF78765E),
    background: BackgroundStyle.flat, surfaceStyle: SurfaceStyle.paperRuled,
    displayFont: DisplayFont.serif, energy: ThemeEnergy.veryLow, personality: ThemePersonality.elegant,
    brightness: Brightness.light, motion: MotionProfile(breathingGlow: true),
  );

  static const velocity = AppPalette(
    id: 'velocity', name: 'Velocity', emoji: '⚡',
    bg: Color(0xFFF5F5F3), surface: Color(0xFFFFFFFF), surfaceHi: Color(0xFFEFEFEF),
    primary: Color(0xFFE0102A), secondary: Color(0xFF4A4A4A), accent: Color(0xFFE0102A),
    spark: Color(0xFFF5D300), on: Color(0xFF0A0A0A), muted: Color(0xFF7A7A78),
    background: BackgroundStyle.flat, surfaceStyle: SurfaceStyle.panelBorder,
    energy: ThemeEnergy.veryHigh, personality: ThemePersonality.energetic,
    brightness: Brightness.light, motion: MotionProfile(movingStripes: true),
  );

  static const aero = AppPalette(
    id: 'aero', name: 'Aero', emoji: '🌤️',
    bg: Color(0xFFF6EFE7), surface: Color(0xFFFBF6F0), surfaceHi: Color(0xFFF3EAE0),
    primary: Color(0xFFD9694A), secondary: Color(0xFF6C8B5E), accent: Color(0xFFD9694A),
    spark: Color(0xFFE0A24E), on: Color(0xFF2B241E), muted: Color(0xFF8A7E71),
    surfaceStyle: SurfaceStyle.glass,   // the one new pack that keeps frosted glass —
                                        // "glassmorphism done right": soft & warm, not neon
    energy: ThemeEnergy.low, personality: ThemePersonality.minimal,
    brightness: Brightness.light,
  );

  static const riot = AppPalette(
    id: 'riot', name: 'Riot', emoji: '💢',
    bg: Color(0xFFDFFA3E), surface: Color(0xFFFFFFFF), surfaceHi: Color(0xFFF5F5F5),
    primary: Color(0xFFFF2E9A), secondary: Color(0xFF1C63C7), accent: Color(0xFFFF2E9A),
    spark: Color(0xFFFF2E9A), on: Color(0xFF111111), muted: Color(0xFF4D5A12),
    background: BackgroundStyle.flat, surfaceStyle: SurfaceStyle.panelBorder,
    energy: ThemeEnergy.veryHigh, personality: ThemePersonality.energetic,
    brightness: Brightness.light, motion: MotionProfile(movingStripes: true),
  );

  static const loom = AppPalette(
    id: 'loom', name: 'Loom', emoji: '🧵',
    bg: Color(0xFFEDE4D3), surface: Color(0xFFF7F1E5), surfaceHi: Color(0xFFF1E9D8),
    primary: Color(0xFF3E4C7A), secondary: Color(0xFFB98A3D), accent: Color(0xFF3E4C7A),
    spark: Color(0xFFB4472E), on: Color(0xFF2B2A3A), muted: Color(0xFF867F68),
    background: BackgroundStyle.flat, surfaceStyle: SurfaceStyle.flatOutlined,
    energy: ThemeEnergy.medium, personality: ThemePersonality.nostalgic,
    brightness: Brightness.light,
  );

  static const toon = AppPalette(
    id: 'toon', name: 'Toon', emoji: '🎈',
    bg: Color(0xFFFFF4D6), surface: Color(0xFFFFFFFF), surfaceHi: Color(0xFFFFF9E8),
    primary: Color(0xFFFF4B3E), secondary: Color(0xFF3DBE5C), accent: Color(0xFFFF4B3E),
    spark: Color(0xFF3EA8FF), on: Color(0xFF171512), muted: Color(0xFF8A7F5E),
    background: BackgroundStyle.flat, surfaceStyle: SurfaceStyle.panelBorder,
    energy: ThemeEnergy.high, personality: ThemePersonality.playful,
    brightness: Brightness.light, motion: MotionProfile(idleWobble: true, breathingGlow: true),
  );

  static const comic = AppPalette(
    id: 'comic', name: 'Comic', emoji: '💥',
    bg: Color(0xFFF4F1E8), surface: Color(0xFFFFFFFF), surfaceHi: Color(0xFFF7F4EC),
    primary: Color(0xFFE4231C), secondary: Color(0xFF4A8CE0), accent: Color(0xFFE4231C),
    spark: Color(0xFFFFD400), on: Color(0xFF0E0E10), muted: Color(0xFF8A8478),
    background: BackgroundStyle.flat, surfaceStyle: SurfaceStyle.panelBorder,
    energy: ThemeEnergy.high, personality: ThemePersonality.playful,
    brightness: Brightness.light, motion: MotionProfile(movingStripes: true, breathingGlow: true),
  );

  static const all = [
    crimson, aurora, midnight, sakura,
    philately, collage, cyberpunk, nihon, terminal, quest, tactile, clay,
    ledger, velocity, aero, riot, loom, toon, comic,
  ];

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

  /// A border/hairline/highlight wash appropriate to the active palette's
  /// brightness — white-based on a dark palette, black-based on a light one.
  /// Use this instead of a literal `Colors.white.withValues(...)` wash, which
  /// only reads correctly when every theme was dark.
  static Color hairline(double alpha) =>
      (active.brightness == Brightness.dark ? Colors.white : Colors.black).withValues(alpha: alpha);

  /// A shadow/scrim tint. Conventionally dark regardless of palette
  /// brightness — a cast shadow reads as "dark" under both a light and dark
  /// surface — so this is currently equivalent to a literal black wash on
  /// every palette. Named for clarity and a single point of change.
  static Color scrim(double alpha) => Colors.black.withValues(alpha: alpha);
}

class AppTheme {
  const AppTheme._();

  /// Build the ThemeData for the currently-active palette (dark or light,
  /// per `p.brightness`). Called whenever the theme changes so Material
  /// widgets (buttons, chips, inputs) re-skin too. Kept as `dark()` for the
  /// existing two call sites in app.dart — the name predates light-palette
  /// support and isn't worth a rename mid-rollout.
  static ThemeData dark() {
    final p = AppColors.active;
    // Containers + outlines derived from the palette so every pack is coherent.
    Color container(Color c) => Color.alphaBlend(c.withValues(alpha: 0.28), p.surface);
    final outline = Color.alphaBlend(p.muted.withValues(alpha: 0.45), p.bg);
    final outlineVariant = Color.alphaBlend(p.muted.withValues(alpha: 0.22), p.bg);

    final schemeBuilder = p.brightness == Brightness.dark ? ColorScheme.dark : ColorScheme.light;
    final scheme = schemeBuilder(
      brightness: p.brightness,
      primary: p.primary,
      onPrimary: p.onPrimaryOverride ?? Colors.white,
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
          minimumSize: const Size.fromHeight(50), foregroundColor: p.onPrimaryOverride ?? Colors.white,
          backgroundColor: p.primary, textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.hairline(0.06),
        selectedColor: p.primary,
        side: BorderSide(color: AppColors.hairline(0.12)),
        labelStyle: TextStyle(color: p.on, fontWeight: FontWeight.w600),
        secondaryLabelStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true, fillColor: AppColors.hairline(0.05),
        hintStyle: TextStyle(color: p.muted),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: AppColors.hairline(0.12))),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: AppColors.hairline(0.12))),
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

  static String? _fontFamilyFor(DisplayFont f) => switch (f) {
        DisplayFont.serif => 'serif',
        DisplayFont.mono => 'monospace',
        DisplayFont.defaultSans => null,
      };

  static TextTheme _typography(TextTheme t, AppPalette p) {
    final family = _fontFamilyFor(p.displayFont);
    return t.copyWith(
      headlineLarge: t.headlineLarge?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.5, color: p.on, fontFamily: family),
      headlineMedium: t.headlineMedium?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.5, color: p.on, fontFamily: family),
      titleLarge: t.titleLarge?.copyWith(fontWeight: FontWeight.w700, color: p.on, fontFamily: family),
      titleMedium: t.titleMedium?.copyWith(fontWeight: FontWeight.w700, color: p.on, fontFamily: family),
      bodyMedium: t.bodyMedium?.copyWith(color: p.on, height: 1.4),
      bodySmall: t.bodySmall?.copyWith(color: p.muted, height: 1.35),
      labelLarge: t.labelLarge?.copyWith(fontWeight: FontWeight.w700),
    );
  }
}
