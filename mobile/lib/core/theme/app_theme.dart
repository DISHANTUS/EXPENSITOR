import 'package:animations/animations.dart';
import 'package:flutter/material.dart';

/// Aurora design language (Sprint UI-X) — dark-first, premium, "living companion".
class AppColors {
  const AppColors._();
  static const bg = Color(0xFF0B1020);
  static const surface = Color(0xFF141B2D);
  static const surfaceHi = Color(0xFF1B2540);
  static const primary = Color(0xFF7C5CFF);   // violet
  static const secondary = Color(0xFF00D4FF); // cyan
  static const accent = Color(0xFFFF5FBF);    // pink
  static const on = Color(0xFFEAF0FF);
  static const muted = Color(0xFF9AA6C7);

  static const aurora = [primary, secondary, accent];
  static const gradient = LinearGradient(colors: [primary, secondary], begin: Alignment.centerLeft, end: Alignment.centerRight);
  static const gradientFull = LinearGradient(colors: [primary, secondary, accent], begin: Alignment.topLeft, end: Alignment.bottomRight);
}

class AppTheme {
  const AppTheme._();

  static ThemeData dark() {
    const scheme = ColorScheme.dark(
      brightness: Brightness.dark,
      primary: AppColors.primary,
      onPrimary: Colors.white,
      primaryContainer: Color(0xFF2A2363),
      onPrimaryContainer: AppColors.on,
      secondary: AppColors.secondary,
      onSecondary: Color(0xFF00222B),
      secondaryContainer: Color(0xFF103040),
      onSecondaryContainer: Color(0xFFB8ECFF),
      tertiary: AppColors.accent,
      onTertiary: Colors.white,
      tertiaryContainer: Color(0xFF4A1E3A),
      onTertiaryContainer: Color(0xFFFFD6EE),
      surface: AppColors.surface,
      onSurface: AppColors.on,
      surfaceContainerHighest: AppColors.surfaceHi,
      onSurfaceVariant: AppColors.muted,
      outline: Color(0xFF3A4360),
      outlineVariant: Color(0xFF2A3350),
      error: Color(0xFFFF6B7A),
    );

    final base = ThemeData(colorScheme: scheme, useMaterial3: true, scaffoldBackgroundColor: AppColors.bg);
    return base.copyWith(
      textTheme: _typography(base.textTheme),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent, elevation: 0, scrolledUnderElevation: 0,
        centerTitle: false, titleTextStyle: TextStyle(color: AppColors.on, fontSize: 20, fontWeight: FontWeight.w700),
        iconTheme: IconThemeData(color: AppColors.on),
      ),
      cardTheme: CardThemeData(
        color: AppColors.surface, elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        margin: const EdgeInsets.symmetric(vertical: 6),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(50), foregroundColor: Colors.white,
          backgroundColor: AppColors.primary, textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: Colors.white.withValues(alpha: 0.06),
        selectedColor: AppColors.primary,
        side: BorderSide(color: Colors.white.withValues(alpha: 0.12)),
        labelStyle: const TextStyle(color: AppColors.on, fontWeight: FontWeight.w600),
        secondaryLabelStyle: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true, fillColor: Colors.white.withValues(alpha: 0.05),
        hintStyle: const TextStyle(color: AppColors.muted),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.12))),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.12))),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: const BorderSide(color: AppColors.primary, width: 1.5)),
      ),
      dividerTheme: const DividerThemeData(color: Color(0xFF2A3350)),
      pageTransitionsTheme: const PageTransitionsTheme(builders: {
        TargetPlatform.android: FadeThroughPageTransitionsBuilder(),
        TargetPlatform.iOS: FadeThroughPageTransitionsBuilder(),
      }),
    );
  }

  static TextTheme _typography(TextTheme t) => t.copyWith(
        headlineLarge: t.headlineLarge?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.5, color: AppColors.on),
        headlineMedium: t.headlineMedium?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.5, color: AppColors.on),
        titleLarge: t.titleLarge?.copyWith(fontWeight: FontWeight.w700, color: AppColors.on),
        titleMedium: t.titleMedium?.copyWith(fontWeight: FontWeight.w700, color: AppColors.on),
        bodyMedium: t.bodyMedium?.copyWith(color: AppColors.on, height: 1.4),
        bodySmall: t.bodySmall?.copyWith(color: AppColors.muted, height: 1.35),
        labelLarge: t.labelLarge?.copyWith(fontWeight: FontWeight.w700),
      );
}
