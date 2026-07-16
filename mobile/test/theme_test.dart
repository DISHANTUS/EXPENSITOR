import 'package:expensitor_mobile/core/theme/app_theme.dart';
import 'package:expensitor_mobile/core/theme/theme_voice.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _expectedIds = [
  'crimson', 'aurora', 'midnight', 'sakura',
  'philately', 'collage', 'cyberpunk', 'nihon', 'terminal', 'quest', 'tactile', 'clay',
  'ledger', 'velocity', 'aero', 'riot', 'loom', 'toon', 'comic',
];

void main() {
  group('AppPalettes', () {
    test('all 19 packs are registered, each with a unique id', () {
      final ids = AppPalettes.all.map((p) => p.id).toList();
      expect(ids.toSet(), _expectedIds.toSet());
      expect(ids.length, ids.toSet().length); // no duplicate ids
    });

    test('byId falls back to crimson for an unknown id', () {
      expect(AppPalettes.byId('does-not-exist').id, 'crimson');
      expect(AppPalettes.byId(null).id, 'crimson');
    });

    test('the 4 legacy packs keep their original defaults untouched', () {
      // Byte-for-byte regression check: extending AppPalette must not change
      // how the pre-existing packs look or behave.
      for (final p in [AppPalettes.crimson, AppPalettes.aurora, AppPalettes.midnight, AppPalettes.sakura]) {
        expect(p.background, BackgroundStyle.aurora, reason: '${p.id} background');
        expect(p.surfaceStyle, SurfaceStyle.glass, reason: '${p.id} surfaceStyle');
        expect(p.displayFont, DisplayFont.defaultSans, reason: '${p.id} displayFont');
        expect(p.energy, ThemeEnergy.medium, reason: '${p.id} energy');
        expect(p.brightness, Brightness.dark, reason: '${p.id} brightness');
        expect(p.onPrimaryOverride, isNull, reason: '${p.id} onPrimaryOverride');
        expect(p.motion.idleWobble, isFalse, reason: '${p.id} motion');
        expect(p.motion.movingStripes, isFalse, reason: '${p.id} motion');
      }
    });

    test('every pack builds a ThemeData without throwing, in both brightness modes', () {
      for (final p in AppPalettes.all) {
        AppColors.active = p;
        expect(() => AppTheme.dark(), returnsNormally, reason: p.id);
        final theme = AppTheme.dark();
        expect(theme.colorScheme.brightness, p.brightness, reason: p.id);
      }
      AppColors.active = AppPalettes.crimson; // restore the default for other tests
    });

    test('bright/pastel primaries all carry an onPrimaryOverride for readable button text', () {
      // A handful of accents are light/saturated enough that white text would
      // fail contrast — this is a lightweight guard that the ones we know
      // about (Clay, Quest, Cyberpunk, Terminal) keep their override.
      const needsOverride = {'clay', 'quest', 'cyberpunk', 'terminal'};
      for (final p in AppPalettes.all.where((p) => needsOverride.contains(p.id))) {
        expect(p.onPrimaryOverride, isNotNull, reason: p.id);
      }
    });
  });

  group('themeVoice', () {
    test('futuristic prefixes every line, never touches embedded numbers', () {
      final out = themeVoice('You spent ₹610 today.\nSaved 12%.', ThemePersonality.futuristic);
      expect(out, '> You spent ₹610 today.\n> Saved 12%.');
    });

    test('playful/energetic swap only the final period for an exclamation mark', () {
      expect(themeVoice('You saved ₹1,240 this week.', ThemePersonality.playful), 'You saved ₹1,240 this week!');
      expect(themeVoice('You saved ₹1,240 this week.', ThemePersonality.energetic), 'You saved ₹1,240 this week!');
      // No trailing period → left alone (never invents punctuation mid-sentence).
      expect(themeVoice('Nice one', ThemePersonality.playful), 'Nice one');
    });

    test('elegant/minimal/nostalgic leave the text untouched', () {
      const text = 'You spent ₹610 today.';
      expect(themeVoice(text, ThemePersonality.elegant), text);
      expect(themeVoice(text, ThemePersonality.minimal), text);
      expect(themeVoice(text, ThemePersonality.nostalgic), text);
    });

    test('never alters a number, date, or currency symbol embedded mid-sentence', () {
      const text = 'Ravi owes you ₹5,000, due Jul 1.';
      for (final p in ThemePersonality.values) {
        final out = themeVoice(text, p);
        expect(out.contains('₹5,000'), isTrue, reason: p.name);
        expect(out.contains('Jul 1'), isTrue, reason: p.name);
      }
    });
  });
}
