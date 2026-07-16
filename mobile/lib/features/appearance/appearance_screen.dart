import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_orb.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/glass.dart';
import '../../core/theme/theme_controller.dart';

/// Theme Studio — pick a theme pack. Each card previews that pack's orb and a
/// real [GlassCard] surface (rendered in *that* pack's surface style, not a
/// generic mock, so a Ledger or Terminal card looks like Ledger or Terminal
/// here too), and tapping applies it live across the whole app (persisted
/// across restarts).
class AppearanceScreen extends ConsumerWidget {
  const AppearanceScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final active = ref.watch(themeProvider);
    return CompanionScaffold(
      title: 'Appearance',
      commentary: 'Pick a look — the whole app, and my orb, follow your theme.',
      mood: CompanionMood.happy,
      child: GridView.builder(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 32),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 0.78,
        ),
        itemCount: AppPalettes.all.length,
        itemBuilder: (_, i) {
          final pack = AppPalettes.all[i];
          return _ThemeCard(
            pack: pack,
            selected: pack.id == active.id,
            onTap: () => ref.read(themeProvider.notifier).select(pack),
          );
        },
      ),
    );
  }
}

class _ThemeCard extends StatelessWidget {
  const _ThemeCard(
      {required this.pack, required this.selected, required this.onTap});
  final AppPalette pack;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
            color: selected ? pack.primary : Colors.transparent, width: 2),
        boxShadow: selected
            ? [
                BoxShadow(
                    color: pack.primary.withValues(alpha: 0.35),
                    blurRadius: 18,
                    offset: const Offset(0, 6))
              ]
            : null,
      ),
      // A pack.bg-colored backing behind the card: a glass-style pack's
      // BackdropFilter blurs whatever's already painted behind it, which —
      // without this — is the REAL active theme's background, not the
      // pack being previewed. Previewing a dark glass pack while a light
      // theme is active would otherwise wash the card out grey.
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: Stack(
          children: [
            Positioned.fill(child: ColoredBox(color: pack.bg)),
            GlassCard(
              palette: pack,
              radius: 18,
              padding: const EdgeInsets.all(12),
              onTap: onTap,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    children: [
                      CompanionOrb(
                          state: OrbState.celebrating, size: 30, palette: pack),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(pack.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                                color: pack.on,
                                fontWeight: FontWeight.w800,
                                fontSize: 13)),
                      ),
                      if (selected)
                        Icon(Icons.check_circle, color: pack.primary, size: 18),
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(pack.emoji, style: const TextStyle(fontSize: 13)),
                  const SizedBox(height: 10),
                  Row(children: [
                    for (final c in [
                      pack.primary,
                      pack.secondary,
                      pack.accent,
                      pack.spark
                    ])
                      Container(
                        width: 14,
                        height: 14,
                        margin: const EdgeInsets.only(right: 5),
                        decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: c,
                            border: Border.all(
                                color: pack.on.withValues(alpha: 0.2))),
                      ),
                  ]),
                  const SizedBox(height: 10),
                  // A sample surface — a real GlassCard in this pack's own surface style,
                  // so the preview is never lying about what the theme looks like.
                  Expanded(
                    child: GlassCard(
                      palette: pack,
                      radius: 12,
                      padding: const EdgeInsets.all(10),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                              height: 6,
                              width: 60,
                              decoration: BoxDecoration(
                                  color: pack.on.withValues(alpha: 0.85),
                                  borderRadius: BorderRadius.circular(3))),
                          const SizedBox(height: 6),
                          Container(
                              height: 5,
                              width: 90,
                              decoration: BoxDecoration(
                                  color: pack.muted,
                                  borderRadius: BorderRadius.circular(3))),
                          const SizedBox(height: 10),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 5),
                            decoration: BoxDecoration(
                                color: pack.primary,
                                borderRadius: BorderRadius.circular(10)),
                            child: Text('Button',
                                style: TextStyle(
                                    color:
                                        pack.onPrimaryOverride ?? Colors.white,
                                    fontWeight: FontWeight.w700,
                                    fontSize: 10)),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
