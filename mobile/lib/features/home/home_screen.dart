import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:table_calendar/table_calendar.dart';

import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_orb.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/companion/greeting.dart';
import '../../core/companion/home_stats_repository.dart';
import '../../core/format/dates.dart';
import '../../core/theme/glass.dart';
import '../calendar/calendar_models.dart';
import '../calendar/calendar_repository.dart';
import 'add_event_sheet.dart';
import 'dashboard_repository.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  DateTime _focused = DateTime.now();

  @override
  Widget build(BuildContext context) {
    final brief = ref.watch(dailyBriefProvider);
    final month = ref.watch(monthViewProvider((year: _focused.year, month: _focused.month)));
    final registry = ref.watch(markerRegistryProvider).valueOrNull ?? fallbackMarkers;
    final monthData = month.valueOrNull;
    // Advary's contextual thought now lives INSIDE the one companion bubble (no
    // second orb) — and gives the single orb its mood (concerned on budget pressure).
    final thought = ref.watch(homeThoughtProvider).valueOrNull;

    return CompanionScaffold(
      title: 'Home',
      // Home is the ONLY screen with the live daily companion greeting + mood
      // rotation; timeGreeting() is the fallback before the live one loads.
      showGreeting: true,
      commentary: timeGreeting(),
      mood: thought?.mood == 'concerned'
          ? CompanionMood.concerned
          : moodFromSeverity(brief.valueOrNull?.severity),
      extraLines: thought?.lines ?? const [],
      actions: [
        IconButton(
          tooltip: 'Add to calendar',
          icon: const Icon(Icons.add),
          onPressed: () => showAddEventSheet(context),
        ),
      ],
      child: ListView(
        children: [
          const _QuickActions(),
          const _MemoryStrip(),
          Card(
            margin: const EdgeInsets.fromLTRB(12, 4, 12, 8),
            child: Padding(
              padding: const EdgeInsets.all(4),
              child: TableCalendar<void>(
                firstDay: DateTime.utc(2000, 1, 1),
                lastDay: DateTime.utc(2100, 12, 31),
                focusedDay: _focused,
                headerStyle: const HeaderStyle(formatButtonVisible: false, titleCentered: true),
                availableGestures: AvailableGestures.horizontalSwipe,
                onPageChanged: (f) => setState(() => _focused = f),
                onDaySelected: (selected, _) {
                  // A marked day holds a memory — Advary reacts before you dive in.
                  final cell = monthData?.cell(selected);
                  if (cell != null && cell.markers.isNotEmpty) {
                    _showDateReaction(context, selected);
                  } else {
                    context.go('/date/${ymd(selected)}');
                  }
                },
                calendarBuilders: CalendarBuilders(
                  // Living Calendar: only meaningful (marked) dates animate — a crown
                  // bounces, income hops, a goal pulses — everything else stays still.
                  markerBuilder: (context, day, _) {
                    final cell = monthData?.cell(day);
                    if (cell == null || cell.markers.isEmpty) return const SizedBox.shrink();
                    final emojis = (cell.markers.toList()..sort(_markerPriority))
                        .take(3)
                        .map((k) => (registry[k] ?? fallbackMarkers[k])?.icon ?? '')
                        .where((e) => e.isNotEmpty)
                        .toList();
                    if (emojis.isEmpty) return const SizedBox.shrink();
                    return Padding(
                      padding: const EdgeInsets.only(top: 27),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [for (final e in emojis) _LivingMarker(e)],
                      ),
                    );
                  },
                ),
              ),
            ),
          ),
          if (month.isLoading)
            const Padding(padding: EdgeInsets.all(8), child: Center(child: Text('Loading month…'))),
          const _Legend(),
          // Previews of your story, future and people (below the calendar).
          const _LivingCards(),
          const SizedBox(height: 12),
        ],
      ),
    );
  }
}

/// A compact command-centre grid right under the companion — fast jumps to the
/// places you use most, so Home isn't only previews + drawer.
class _QuickActions extends StatelessWidget {
  const _QuickActions();

  static const _actions = <(String, IconData, String)>[
    ('Plan Today', Icons.today_outlined, '/plan-today'),
    ('Chat', Icons.chat_bubble_outline, '/advisor'),
    ('Timeline', Icons.timeline, '/timeline'),
    ('Future Me', Icons.auto_graph, '/future-me'),
    ('Converter', Icons.currency_exchange, '/convert'),
    ('Settings', Icons.settings_outlined, '/settings'),
  ];

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 2),
      child: GridView.count(
        crossAxisCount: 3,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        mainAxisSpacing: 8,
        crossAxisSpacing: 8,
        childAspectRatio: 1.55,
        children: [
          for (final (label, icon, route) in _actions)
            GlassCard(
              padding: const EdgeInsets.all(6),
              onTap: () => context.go(route),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(icon, color: cs.primary, size: 22),
                  const SizedBox(height: 5),
                  Text(label, style: tt.labelSmall, textAlign: TextAlign.center, maxLines: 1, overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// The Home Memory Strip — "37 days with Advary · 🏆 4 goals · 💰 ₹18,200 · …".
/// Makes Home feel personal from data that already exists. Hidden until there's
/// something worth showing.
class _MemoryStrip extends ConsumerWidget {
  const _MemoryStrip();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final stats = ref.watch(homeStatsProvider).valueOrNull;
    if (stats == null) return const SizedBox.shrink();
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;

    String money(double v) =>
        '${stats.currency} ${v.toStringAsFixed(0).replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},')}';
    final chips = <(String, String)>[
      if (stats.goalsCompleted > 0) ('🏆', '${stats.goalsCompleted} goal${stats.goalsCompleted == 1 ? '' : 's'}'),
      if (stats.totalSaved > 0) ('💰', money(stats.totalSaved)),
      if (stats.relationshipCount > 0) ('❤️', '${stats.relationshipCount} ${stats.relationshipCount == 1 ? 'person' : 'people'}'),
      if (stats.biggestWin != null) ('🎯', stats.biggestWin!),
    ];

    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 2),
      child: GlassCard(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${stats.daysWithAdvary} day${stats.daysWithAdvary == 1 ? '' : 's'} with Advary',
                style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
            if (stats.strongestHabit != null)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text('Strongest habit: ${stats.strongestHabit}',
                    style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant)),
              ),
            if (chips.isNotEmpty) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final (emoji, label) in chips)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.06),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text('$emoji  $label', style: tt.labelMedium),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _QuickCard {
  const _QuickCard(this.label, this.icon, this.route);
  final String label;
  final IconData icon;
  final String route;
}

// Fallback shortcuts shown while the live preview cards load (or if they fail) —
// Home never loses its navigation.
const _quick = <_QuickCard>[
  _QuickCard('Plan Today', Icons.today_outlined, '/plan-today'),
  _QuickCard('Your Story', Icons.timeline, '/timeline'),
  _QuickCard('Future You', Icons.auto_graph, '/future-me'),
  _QuickCard('People', Icons.favorite_border, '/relationships'),
];

/// Living Quick Cards — previews of the user's story, future and people, plus
/// today's focus. They read like glimpses, not buttons; tapping opens the page.
class _LivingCards extends ConsumerWidget {
  const _LivingCards();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cards = ref.watch(homeCardsProvider).valueOrNull;
    if (cards == null || cards.isEmpty) return const _QuickFallback();
    return SizedBox(
      height: 132,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        itemCount: cards.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (_, i) => _PreviewCard(cards[i]),
      ),
    );
  }
}

class _PreviewCard extends StatelessWidget {
  const _PreviewCard(this.card);
  final HomeCard card;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    return SizedBox(
      width: 212,
      child: GlassCard(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
        onTap: () => context.go(card.route),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(card.icon, style: const TextStyle(fontSize: 16)),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(card.title.toUpperCase(),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: tt.labelSmall?.copyWith(
                          color: cs.onSurfaceVariant, letterSpacing: 0.6, fontWeight: FontWeight.w600)),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(card.headline,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w700, height: 1.2)),
            if (card.subtitle != null && card.subtitle!.isNotEmpty) ...[
              const SizedBox(height: 4),
              Expanded(
                child: Text(card.subtitle!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant, height: 1.25)),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _QuickFallback extends StatelessWidget {
  const _QuickFallback();
  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 92,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        children: [
          for (final q in _quick)
            SizedBox(
              width: 104,
              child: Card(
                child: InkWell(
                  onTap: () => context.go(q.route),
                  borderRadius: BorderRadius.circular(12),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(q.icon, color: Theme.of(context).colorScheme.primary),
                      const SizedBox(height: 6),
                      Text(q.label, style: Theme.of(context).textTheme.labelMedium, textAlign: TextAlign.center),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

// Most celebratory / meaningful markers sort first (so the biggest animation leads).
const _priorityEmojis = ['👑', '🎯', '🎉', '🎓', '✈️', '❤️', '💗', '🤝', '💰', '💼', '🟢', '📅', '🔴'];
int _markerPriority(String a, String b) {
  int rank(String k) {
    for (var i = 0; i < _priorityEmojis.length; i++) {
      if (k.contains(_priorityEmojis[i]) || _priorityEmojis[i].contains(k)) return i;
    }
    return 99;
  }
  return rank(a).compareTo(rank(b));
}

enum _MarkerKind { crown, income, goal, relationship, travel, concern, gentle }

_MarkerKind _kindFor(String e) {
  if (e.contains('👑')) return _MarkerKind.crown;
  if (e.contains('🎯') || e.contains('🎉') || e.contains('🎓')) return _MarkerKind.goal;
  if (e.contains('💰') || e.contains('💼')) return _MarkerKind.income;
  if (e.contains('❤') || e.contains('💗') || e.contains('🤝')) return _MarkerKind.relationship;
  if (e.contains('✈')) return _MarkerKind.travel;
  if (e.contains('🔴')) return _MarkerKind.concern;
  return _MarkerKind.gentle;
}

/// One marked date brought to life. A single lightweight controller drives a
/// subtle, type-specific motion — float/tilt/hop/pulse/beat — so only meaningful
/// dates move and the calendar never becomes a distracting light show.
class _LivingMarker extends StatefulWidget {
  const _LivingMarker(this.emoji);
  final String emoji;

  @override
  State<_LivingMarker> createState() => _LivingMarkerState();
}

class _LivingMarkerState extends State<_LivingMarker> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 2600))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final kind = _kindFor(widget.emoji);
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) {
        final tau = _c.value * 2 * math.pi;
        final s = math.sin(tau);
        double dy = s * 1.1, rot = 0, scale = 1;
        switch (kind) {
          case _MarkerKind.crown:
            dy = s * 1.8;
            rot = s * 0.18;                       // tilt left/right like a crown
          case _MarkerKind.income:
            dy = -s.abs() * 2.4;                  // little hops
          case _MarkerKind.goal:
            scale = 1 + s * 0.16;                 // pulse
          case _MarkerKind.relationship:
            scale = 1 + (s * 0.5 + 0.5) * 0.18;   // heartbeat
          case _MarkerKind.travel:
            dy = s * 2.0;
            rot = s * 0.12;                       // gentle takeoff sway
          case _MarkerKind.concern:
            scale = 1 + s * 0.05;                 // slow, subdued breathing
          case _MarkerKind.gentle:
            dy = s * 1.0;
        }
        return Transform.translate(
          offset: Offset(0, -dy),
          child: Transform.rotate(
            angle: rot,
            child: Transform.scale(scale: scale, child: Text(widget.emoji, style: const TextStyle(fontSize: 11))),
          ),
        );
      },
    );
  }
}

/// Tap a marked date → Advary reacts (the calendar as memory). A glass sheet
/// with the orb wearing the day's mood + a warm one-liner, and a way in.
void _showDateReaction(BuildContext context, DateTime day) {
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: Colors.transparent,
    builder: (_) => _DateReactionSheet(day: day),
  );
}

class _DateReactionSheet extends ConsumerWidget {
  const _DateReactionSheet({required this.day});
  final DateTime day;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final key = ymd(day);
    final reaction = ref.watch(dateReactionProvider(key));
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;

    final r = reaction.valueOrNull;
    final orb = switch (r?.mood) {
      'celebrating' => OrbState.celebrating,
      'concerned' => OrbState.concerned,
      _ => OrbState.idle,
    };
    final line = r?.line ?? (reaction.hasError ? 'Let me look at that day with you.' : 'Remembering that day…');

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
        child: GlassCard(
          padding: const EdgeInsets.fromLTRB(16, 18, 16, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CompanionOrb(state: orb, size: 64),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(
                        r != null ? '${r.emoji}  $line' : line,
                        style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w600, height: 1.3),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton.tonalIcon(
                  onPressed: () {
                    Navigator.of(context).pop();
                    context.go('/date/$key');
                  },
                  icon: const Icon(Icons.arrow_forward, size: 18),
                  label: const Text('Open this day'),
                  style: FilledButton.styleFrom(
                      foregroundColor: cs.onSurface,
                      backgroundColor: Colors.white.withValues(alpha: 0.08)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend();
  @override
  Widget build(BuildContext context) {
    const items = [
      ('🔴', 'Over budget'),
      ('👑', 'Saved'),
      ('🟢', 'Within budget'),
      ('💼', 'Income'),
      ('📅', 'Event'),
    ];
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
      child: Wrap(
        spacing: 14,
        runSpacing: 6,
        children: [
          for (final (emoji, label) in items)
            Text('$emoji $label', style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}
