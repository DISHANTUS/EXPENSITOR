import 'app_theme.dart';

/// Surface-level phrasing per [ThemePersonality] — applied to *already-computed*
/// companion text (a greeting, a chat reply). Never changes a number, adds a
/// fact, or alters what the engines/LLM actually concluded; only touches line
/// prefixes and final punctuation, never the middle of a sentence, so a
/// currency amount or date embedded in the text is always left exactly as-is.
/// A 6-personality mapping, not one bespoke voice per theme — a 16th theme
/// gets sensible phrasing automatically just by picking a personality.
String themeVoice(String text, ThemePersonality personality) {
  final t = text.trimRight();
  if (t.isEmpty) return t;
  switch (personality) {
    case ThemePersonality.futuristic:
      // Terminal / Cyberpunk / Quest read like a status readout.
      return t.split('\n').map((l) => l.trim().isEmpty ? l : '> ${l.trim()}').join('\n');
    case ThemePersonality.playful:
    case ThemePersonality.energetic:
      // A touch of exclamatory energy — only the final punctuation, never
      // mid-sentence, so a "₹1,240." embedded in the text is untouched.
      return t.endsWith('.') ? '${t.substring(0, t.length - 1)}!' : t;
    case ThemePersonality.elegant:
    case ThemePersonality.minimal:
    case ThemePersonality.nostalgic:
      return t;
  }
}
