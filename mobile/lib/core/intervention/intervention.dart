import 'package:flutter/material.dart';

/// The generic AI-intervention framework. Advary "noticing something" is ONE
/// system, not one-per-feature: every future trigger (borrowed money, event
/// impact, income verification, a spending-pattern change, a due subscription)
/// just creates an [Intervention]. The orb lights up, the user taps, Advary
/// talks, and — crucially — an answer can produce a structured [Fact] that the
/// timeline / relationships / future explanations all reuse.

enum InterventionTrigger {
  borrowedMoney,
  eventForecast,
  incomeVerification,
  spendingPatternChange,
  subscriptionDue,
  reminder,
  relationshipLearning,
  /// Advary has check-in questions waiting to be answered. Unlike the others
  /// this one doesn't argue its case in the sheet — it points at the Planning
  /// page, where the questions actually live, and offers a ride there.
  pendingQuestions,
  generic,
}

enum InterventionPriority { low, medium, high, urgent }

/// A structured fact distilled from a user's answer — NOT a loose note. e.g.
/// "Kaguya gives me rides" → {type: transport_assistance, person: Kaguya, ...}.
/// Reused by relationship timeline, savings estimates and future explanations.
@immutable
class Fact {
  const Fact({required this.type, this.person, this.attributes = const {}});

  final String type; // e.g. transport_assistance | price_increase | holiday
  final String? person; // e.g. Kaguya / Pranav, when a person is involved
  final Map<String, dynamic> attributes; // freeform: {frequency: daily, est_savings: 900}

  Map<String, dynamic> toJson() => {
        'type': type,
        if (person != null) 'person': person,
        ...attributes,
      };
}

/// One answer option Advary offers. Picking it can mint a [Fact].
@immutable
class InterventionChoice {
  const InterventionChoice(this.label, {this.fact});
  final String label; // e.g. "Friend giving rides"
  final Fact? fact; // the structured fact this answer creates (if any)
}

@immutable
class Intervention {
  const Intervention({
    required this.id,
    required this.trigger,
    required this.title,
    required this.message,
    this.priority = InterventionPriority.medium,
    this.question,
    this.choices = const [],
    this.actionLabel,
    this.actionRoute,
    this.inputLabel,
    this.payload = const {},
  });

  final String id; // stable & unique, e.g. "reminder:<eventId>" — drives dedupe
  final InterventionTrigger trigger;
  final InterventionPriority priority;
  final String title; // short headline, e.g. "🎂 Kaguya's birthday in 3 days"
  final String message; // what Advary says when you open the talk sheet
  final String? question; // if Advary asks something ("Did something change?")
  final List<InterventionChoice> choices; // answer options (each may mint a Fact)
  final String? actionLabel; // primary CTA when there are no choices
  final String? actionRoute; // optional navigation when the action is taken
  final String? inputLabel; // when set, Advary asks for a free-text answer (e.g. a name)
  final Map<String, dynamic> payload; // trigger-specific data

  /// True when Advary is waiting on the user for something, rather than just
  /// mentioning it. Drives the orb's "!" badge — an exclamation should mean
  /// "you owe me an answer", not merely "there's news", or it stops meaning
  /// anything at all.
  bool get wantsAnswer =>
      question != null ||
      choices.isNotEmpty ||
      inputLabel != null ||
      trigger == InterventionTrigger.pendingQuestions;

  Color ringColor(ColorScheme cs) => switch (priority) {
        InterventionPriority.urgent => const Color(0xFFE53935),
        InterventionPriority.high => cs.primary,
        InterventionPriority.medium => const Color(0xFFFFB300),
        InterventionPriority.low => cs.secondary,
      };
}
