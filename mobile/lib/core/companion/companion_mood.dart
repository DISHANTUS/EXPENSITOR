import 'package:flutter/material.dart';

/// The companion's emotional state. Drives the placeholder face + bubble accent
/// until real character art (per mood) is supplied.
enum CompanionMood { happy, neutral, concerned, excited }

CompanionMood moodFromSeverity(String? severity) {
  switch (severity) {
    case 'alert':
    case 'warning':
      return CompanionMood.concerned;
    case 'success':
      return CompanionMood.happy;
    default:
      return CompanionMood.neutral;
  }
}

CompanionMood moodFromClassification(String? classification) {
  switch (classification) {
    case 'over':
      return CompanionMood.concerned;
    case 'saved':
      return CompanionMood.happy;
    default:
      return CompanionMood.neutral;
  }
}

extension CompanionMoodVisual on CompanionMood {
  /// Placeholder glyph; swapped for real art in Sprint 5.
  String get face {
    switch (this) {
      case CompanionMood.happy:
        return '😊';
      case CompanionMood.excited:
        return '🤩';
      case CompanionMood.concerned:
        return '😟';
      case CompanionMood.neutral:
        return '🙂';
    }
  }

  Color color(ColorScheme cs) {
    switch (this) {
      case CompanionMood.happy:
        return Colors.green.shade600;
      case CompanionMood.excited:
        return cs.tertiary;
      case CompanionMood.concerned:
        return cs.error;
      case CompanionMood.neutral:
        return cs.primary;
    }
  }
}
