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

/// Everything Advary currently wants to raise — manual triggers + derived
/// reminders, minus what's been resolved, highest priority first.
final pendingInterventionsProvider = Provider.autoDispose<List<Intervention>>((ref) {
  final st = ref.watch(interventionControllerProvider);
  final reminders = ref.watch(reminderInterventionsProvider).valueOrNull ?? const [];
  final all = [...st.manual, ...reminders].where((i) => !st.resolved.contains(i.id)).toList()
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
