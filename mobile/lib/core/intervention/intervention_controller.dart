import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../format/dates.dart';
import 'intervention.dart';

/// State for the intervention spine: interventions other systems push in, the
/// ids the user has already resolved (so they don't reappear), and the facts
/// minted from answers (kept locally for now — wired to the backend later).
class InterventionState {
  const InterventionState({this.manual = const [], this.resolved = const {}, this.facts = const []});

  final List<Intervention> manual; // future triggers (borrowed money, forecast…) push here
  final Set<String> resolved; // ids dismissed / answered — never shown again
  final List<Fact> facts; // structured facts from answers (reused by timeline later)

  InterventionState copyWith({List<Intervention>? manual, Set<String>? resolved, List<Fact>? facts}) =>
      InterventionState(
        manual: manual ?? this.manual,
        resolved: resolved ?? this.resolved,
        facts: facts ?? this.facts,
      );
}

/// The one place Advary's "I noticed something" lives. Any system creates an
/// intervention via [add]; an answer is captured via [resolve] (optionally with
/// the [Fact] it produced). Debt/forecast/income just become new triggers here.
class InterventionController extends StateNotifier<InterventionState> {
  InterventionController() : super(const InterventionState());

  void add(Intervention i) {
    if (state.manual.any((x) => x.id == i.id) || state.resolved.contains(i.id)) return;
    state = state.copyWith(manual: [...state.manual, i]);
  }

  /// Mark an intervention handled (tapped through, dismissed, or answered).
  /// A produced [Fact] is recorded so the timeline/relationship layer can reuse it.
  void resolve(String id, {Fact? fact}) {
    state = state.copyWith(
      resolved: {...state.resolved, id},
      facts: fact == null ? state.facts : [...state.facts, fact],
    );
  }
}

final interventionControllerProvider =
    StateNotifierProvider<InterventionController, InterventionState>((_) => InterventionController());

// --- First trigger source (DB-independent): upcoming-event reminders ----------

const _occasionEmoji = <String, String>{
  'birthday': '🎂', 'anniversary': '💞', 'travel': '✈️', 'vacation': '✈️',
  'outing': '❤️', 'date': '❤️', 'celebration': '🎉', 'festival': '🪔',
  'graduation': '🎓', 'study': '📚', 'medical': '🏥', 'gaming': '🎮', 'food': '🍔',
};

/// Reads upcoming planned events and turns the next few days' worth into reminder
/// interventions. Read-only (no schema), so it's safe to ship before the Payable
/// backend is verified — and it's the template every later trigger follows.
final reminderInterventionsProvider = FutureProvider.autoDispose<List<Intervention>>((ref) async {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  try {
    final res = await ref.watch(dioProvider).get<dynamic>(
          '/planned-expenses',
          queryParameters: {'status': 'planned', 'limit': 50},
        );
    final items = ((res.data as Map)['items'] as List?) ?? const [];
    final out = <Intervention>[];
    for (final raw in items.whereType<Map>()) {
      final e = raw.cast<String, dynamic>();
      final dateStr = e['planned_date']?.toString();
      if (dateStr == null) continue;
      final date = DateTime.tryParse(dateStr);
      if (date == null) continue;
      final days = DateTime(date.year, date.month, date.day).difference(today).inDays;
      if (days < 0 || days > 3) continue; // only the near horizon
      final title = (e['title'] ?? 'Event').toString();
      final emoji = _occasionEmoji[e['occasion_type']?.toString()] ?? '📅';
      final whenWord = days == 0 ? 'today' : days == 1 ? 'tomorrow' : 'in $days days';
      out.add(Intervention(
        id: 'reminder:${e['id']}',
        trigger: InterventionTrigger.reminder,
        priority: days <= 1 ? InterventionPriority.high : InterventionPriority.medium,
        title: '$emoji $title — $whenWord',
        message: '“$title” is coming up $whenWord (${formatDate(date)}). Want to get ready for it?',
        actionLabel: 'Open the day',
        actionRoute: '/date/${ymd(date)}',
      ));
    }
    return out;
  } on DioException {
    return const []; // the spine never breaks a screen if the fetch fails
  }
});

String _money(String amount, String currency) {
  final n = double.tryParse(amount) ?? 0;
  final s = n == n.roundToDouble() ? n.toStringAsFixed(0) : n.toStringAsFixed(2);
  final sep = s.replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+(?!\d))'), (m) => '${m[1]},');
  return currency.isEmpty ? sep : '$currency $sep';
}

/// Borrowed-money trigger. Tasteful: Advary stays quiet for a far-off debt and
/// only speaks when it's near (≤7 days) or overdue — never "Debt due" spam.
/// (Pass 2 slice 2 adds the "Plan repayment" action backed by forecast_service.)
final payableInterventionsProvider = FutureProvider.autoDispose<List<Intervention>>((ref) async {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  try {
    final res = await ref.watch(dioProvider).get<dynamic>(
          '/payables',
          queryParameters: {'status': 'open', 'limit': 50},
        );
    final items = ((res.data as Map)['items'] as List?) ?? const [];
    final out = <Intervention>[];
    for (final raw in items.whereType<Map>()) {
      final p = raw.cast<String, dynamic>();
      final daysOverdue = (p['days_overdue'] as num?)?.toInt() ?? 0;
      final dueStr = p['due_date']?.toString();
      int? daysUntil;
      if (dueStr != null) {
        final d = DateTime.tryParse(dueStr);
        if (d != null) daysUntil = DateTime(d.year, d.month, d.day).difference(today).inDays;
      }
      final overdue = daysOverdue > 0;
      final soon = daysUntil != null && daysUntil >= 0 && daysUntil <= 7;
      if (!overdue && !soon) continue; // stay quiet otherwise
      final who = (p['source_name'] ?? 'someone').toString();
      final amount = _money((p['converted_amount'] ?? '0').toString(), (p['base_currency'] ?? '').toString());
      final whenWords = overdue
          ? (daysOverdue == 1 ? 'a day overdue' : '$daysOverdue days overdue')
          : (daysUntil == 0 ? 'due today' : daysUntil == 1 ? 'due tomorrow' : 'due in $daysUntil days');
      out.add(Intervention(
        id: 'payable:${p['id']}',
        trigger: InterventionTrigger.borrowedMoney,
        priority: overdue ? InterventionPriority.urgent : InterventionPriority.high,
        title: '🪙 You owe $who $amount',
        message: 'You borrowed $amount from $who — $whenWords. Would you like me to work out a repayment plan?',
        actionLabel: 'Plan repayment',
        actionRoute: '/payable/${p['id']}/repay',
        payload: {'payable_id': p['id'], 'amount': p['converted_amount'], 'currency': p['base_currency'],
                  'due_date': dueStr, 'who': who},
      ));
    }
    return out;
  } on DioException {
    return const [];
  }
});

bool _titleNamesPerson(String title) {
  // "Dinner with Kaguya" / "Kaguya's birthday" already names a person; "Outing"
  // or "Date night" does not — so Advary asks instead of assuming.
  return RegExp(r'\bwith\s+[A-Z][a-zA-Z]+').hasMatch(title) ||
      RegExp(r"[A-Z][a-zA-Z]+['’]s\b").hasMatch(title);
}

/// "Ask, don't assume": when the user plans an outing/date with no named person,
/// Advary gently asks who it's with (consent-based, optional) — one at a time so
/// it never nags. The answer creates a real Person (relationship), not a guess.
final relationshipInterventionsProvider = FutureProvider.autoDispose<List<Intervention>>((ref) async {
  try {
    final res = await ref.watch(dioProvider).get<dynamic>('/planned-expenses', queryParameters: {'limit': 50});
    final items = ((res.data as Map)['items'] as List?) ?? const [];
    for (final raw in items.whereType<Map>()) {
      final e = raw.cast<String, dynamic>();
      final occ = e['occasion_type']?.toString();
      if (occ != 'outing' && occ != 'date') continue;
      final title = (e['title'] ?? '').toString();
      if (title.isEmpty || _titleNamesPerson(title)) continue;
      return [Intervention(
        id: 'rel-name:${e['id']}',
        trigger: InterventionTrigger.relationshipLearning,
        priority: InterventionPriority.low,
        title: '💛 Getting to know you',
        message: 'I noticed you planned "$title". Mind if I ask who it\'s with? '
            "It helps me understand your world — totally optional.",
        inputLabel: 'Their name',
        payload: {'event_id': e['id'], 'occasion': occ, 'title': title},
      )];
    }
    return const [];
  } on DioException {
    return const [];
  }
});

/// Everything Advary currently wants to raise — manual triggers + derived
/// borrowed-money + reminders + relationship questions, minus what's been
/// resolved, highest priority first.
final pendingInterventionsProvider = Provider.autoDispose<List<Intervention>>((ref) {
  final st = ref.watch(interventionControllerProvider);
  final payables = ref.watch(payableInterventionsProvider).valueOrNull ?? const [];
  final reminders = ref.watch(reminderInterventionsProvider).valueOrNull ?? const [];
  final relationship = ref.watch(relationshipInterventionsProvider).valueOrNull ?? const [];
  final all = [...st.manual, ...payables, ...reminders, ...relationship]
      .where((i) => !st.resolved.contains(i.id)).toList()
    ..sort((a, b) => b.priority.index.compareTo(a.priority.index));
  // de-dupe by id (a manual one wins over a derived one with the same id)
  final seen = <String>{};
  return [for (final i in all) if (seen.add(i.id)) i];
});

final hasAttentionProvider = Provider.autoDispose<bool>((ref) => ref.watch(pendingInterventionsProvider).isNotEmpty);

final topInterventionProvider = Provider.autoDispose<Intervention?>((ref) {
  final p = ref.watch(pendingInterventionsProvider);
  return p.isEmpty ? null : p.first;
});
