import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_orb.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/theme_controller.dart';

/// Theme Studio — pick a theme pack. Each card previews that pack's orb, surface,
/// button and calendar markers in its own colours, and tapping applies it live
/// across the whole app (persisted across restarts).
class AppearanceScreen extends ConsumerWidget {
  const AppearanceScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final active = ref.watch(themeProvider);
    return CompanionScaffold(
      title: 'Appearance',
      commentary: 'Pick a look — the whole app, and my orb, follow your theme.',
      mood: CompanionMood.happy,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 32),
        children: [
          for (final pack in AppPalettes.all)
            _ThemeCard(
              pack: pack,
              selected: pack.id == active.id,
              onTap: () => ref.read(themeProvider.notifier).select(pack),
            ),
        ],
      ),
    );
  }
}

class _ThemeCard extends StatelessWidget {
  const _ThemeCard({required this.pack, required this.selected, required this.onTap});
  final AppPalette pack;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: pack.bg,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: selected ? pack.primary : Colors.white.withValues(alpha: 0.10),
              width: selected ? 2 : 1,
            ),
            boxShadow: selected
                ? [BoxShadow(color: pack.primary.withValues(alpha: 0.35), blurRadius: 22, offset: const Offset(0, 8))]
                : null,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  // Orb preview in this pack's colours (celebrating shows the sparks).
                  CompanionOrb(state: OrbState.celebrating, size: 46, palette: pack),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${pack.emoji}  ${pack.name}',
                            style: tt.titleMedium?.copyWith(color: pack.on, fontWeight: FontWeight.w800)),
                        const SizedBox(height: 6),
                        Row(children: [
                          for (final c in [pack.primary, pack.secondary, pack.accent, pack.spark])
                            Container(
                              width: 18, height: 18,
                              margin: const EdgeInsets.only(right: 6),
                              decoration: BoxDecoration(shape: BoxShape.circle, color: c,
                                  border: Border.all(color: Colors.white.withValues(alpha: 0.18))),
                            ),
                        ]),
                      ],
                    ),
                  ),
                  if (selected) Icon(Icons.check_circle, color: pack.primary),
                ],
              ),
              const SizedBox(height: 14),
              // A sample surface card with a title line + a primary button + markers.
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: pack.surface,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(height: 8, width: 120,
                        decoration: BoxDecoration(color: pack.on.withValues(alpha: 0.85), borderRadius: BorderRadius.circular(4))),
                    const SizedBox(height: 8),
                    Container(height: 6, width: 180,
                        decoration: BoxDecoration(color: pack.muted, borderRadius: BorderRadius.circular(4))),
                    const SizedBox(height: 12),
                    Row(children: [
                      // Button preview
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        decoration: BoxDecoration(color: pack.primary, borderRadius: BorderRadius.circular(12)),
                        child: const Text('Button', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 12)),
                      ),
                      const Spacer(),
                      // Progress-bar preview
                      Expanded(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(6),
                          child: Stack(children: [
                            Container(height: 8, color: Colors.white.withValues(alpha: 0.08)),
                            FractionallySizedBox(
                              widthFactor: 0.6,
                              child: Container(height: 8,
                                  decoration: BoxDecoration(gradient: LinearGradient(colors: [pack.primary, pack.secondary]))),
                            ),
                          ]),
                        ),
                      ),
                    ]),
                    const SizedBox(height: 10),
                    const Text('👑   💰   ❤️   ✈️   🎯', style: TextStyle(fontSize: 16)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
