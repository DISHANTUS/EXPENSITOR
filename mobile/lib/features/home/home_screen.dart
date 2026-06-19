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
import 'did_you_know_card.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  DateTime _focused = DateTime.now();

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final brief = ref.watch(dailyBriefProvider);
    final month = ref.watch(monthViewProvider((year: _focused.year, month: _focused.month)));
    final registry = ref.watch(markerRegistryProvider).valueOrNull ?? fallbackMarkers;
    final monthData = month.valueOrNull;
    // Advary's contextual thought now lives INSIDE the one companion bubble (no
    // second orb) — and gives the single orb its mood (concerned on budget pressure).
    final thoughtAsync = ref.watch(homeThoughtProvider);
    final thought = thoughtAsync.valueOrNull;
    // "Did You Know" appears only when Advary has nothing user-specific to say —
    // so a fact never duplicates the orb's thought. While loading we wait; offline
    // we still offer a fact (facts are local/offline-first).
    final showFact = switch (thoughtAsync) {
      AsyncData(:final value) => value.lines.isEmpty,
      AsyncError() => true,
      _ => false,
    };

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
          // Calendar sits directly under the Quick Actions grid — the most
          // interactive, life-tied element gets the premium Home position.
          // Faint crimson-tinted glass so the calendar reads as part of the
          // Crimson Moon theme, not a black widget dropped onto the page.
          GlassCard(
            margin: const EdgeInsets.fromLTRB(12, 4, 12, 8),
            padding: const EdgeInsets.all(4),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                cs.primary.withValues(alpha: 0.12),
                Colors.black.withValues(alpha: 0.20),
                cs.primary.withValues(alpha: 0.10),
              ],
            ),
            borderColor: cs.primary.withValues(alpha: 0.22),
            child: TableCalendar<void>(
              firstDay: DateTime.utc(2000, 1, 1),
              lastDay: DateTime.utc(2100, 12, 31),
              focusedDay: _focused,
              headerStyle: const HeaderStyle(formatButtonVisible: false, titleCentered: true),
              availableGestures: AvailableGestures.horizontalSwipe,
              // Sliding month transitions — June → July animates sideways.
              pageAnimationEnabled: true,
              pageAnimationDuration: const Duration(milliseconds: 320),
              pageAnimationCurve: Curves.easeInOutCubic,
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
                // Today breathes a soft crimson glow, so the calendar feels alive
                // immediately — no events required.
                todayBuilder: (context, day, _) => _BreathingToday(day: day, color: cs.primary),
                // Living Calendar: only meaningful (marked) dates animate — a crown
                // sparkles, a cake flickers, a plane drifts — everything else still.
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
          if (month.isLoading)
            const Padding(padding: EdgeInsets.all(8), child: Center(child: Text('Loading month…'))),
          const _Legend(),
          // Previews of your story, future and people (below the calendar).
          const _LivingCards(),
          // Facts live in ONE place — only when the orb has nothing personal to
          // say (never duplicated with Advary's own thought).
          if (showFact) const DidYouKnowCard(),
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

  // Each action carries a signature idle motion so the grid feels alive without
  // becoming a light show — labels stay still, only the icons breathe.
  static const _actions = <(String, IconData, String, _ActionMotion)>[
    ('Plan Today', Icons.today_outlined, '/plan-today', _ActionMotion.bounce),
    ('Chat', Icons.chat_bubble_outline, '/advisor', _ActionMotion.pulse),
    ('Timeline', Icons.timeline, '/timeline', _ActionMotion.graph),
    ('Future Me', Icons.auto_graph, '/future-me', _ActionMotion.sparkle),
    ('Converter', Icons.currency_exchange, '/convert', _ActionMotion.swap),
    ('Settings', Icons.settings_outlined, '/settings', _ActionMotion.spin),
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
          for (final (label, icon, route, motion) in _actions)
            GlassCard(
              padding: const EdgeInsets.all(6),
              onTap: () => context.go(route),
              // Crimson-tinted glass over deep black so the glowing icon pops —
              // matches the rest of the Home palette (Crimson Moon).
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  cs.primary.withValues(alpha: 0.16),
                  Colors.black.withValues(alpha: 0.30),
                ],
              ),
              borderColor: cs.primary.withValues(alpha: 0.24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _LivingActionIcon(icon, motion, color: cs.primary, size: 22),
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

/// Signature idle motions for the Quick Action icons. Each is subtle and slow —
/// delight, not distraction.
enum _ActionMotion { bounce, pulse, graph, sparkle, swap, spin }

/// A Quick Action icon brought to life with a single lightweight controller:
/// chat breathes, settings turns, the timeline bobs like a graph, Future Me
/// twinkles, the converter's arrows slide, Plan Today gives a gentle bounce.
class _LivingActionIcon extends StatefulWidget {
  const _LivingActionIcon(this.icon, this.motion, {required this.color, this.size = 22});
  final IconData icon;
  final _ActionMotion motion;
  final Color color;
  final double size;

  @override
  State<_LivingActionIcon> createState() => _LivingActionIconState();
}

class _LivingActionIconState extends State<_LivingActionIcon> with SingleTickerProviderStateMixin {
  late final AnimationController _c;

  @override
  void initState() {
    super.initState();
    final ms = switch (widget.motion) {
      _ActionMotion.spin => 7000,    // slow, near-imperceptible turn
      _ActionMotion.pulse => 1900,
      _ActionMotion.graph => 2300,
      _ActionMotion.sparkle => 2400,
      _ActionMotion.swap => 2100,
      _ActionMotion.bounce => 2600,
    };
    _c = AnimationController(vsync: this, duration: Duration(milliseconds: ms))..repeat();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final icon = Icon(
      widget.icon,
      color: widget.color,
      size: widget.size,
      shadows: [Shadow(color: widget.color.withValues(alpha: 0.55), blurRadius: 12)],
    );
    return AnimatedBuilder(
      animation: _c,
      builder: (_, child) {
        final tau = _c.value * 2 * math.pi;
        final s = math.sin(tau);
        switch (widget.motion) {
          case _ActionMotion.spin:
            return Transform.rotate(angle: _c.value * 2 * math.pi, child: child);
          case _ActionMotion.pulse:
            return Transform.scale(scale: 1 + (s * 0.5 + 0.5) * 0.12, child: child); // breathe 1.0→1.12
          case _ActionMotion.graph:
            return Transform.translate(offset: Offset(0, s * 1.8), child: child);     // bob like a line graph
          case _ActionMotion.swap:
            return Transform.translate(offset: Offset(s * 1.8, 0), child: child);     // arrows slide L/R
          case _ActionMotion.bounce:
            final p = _c.value;
            final b = p < 0.3 ? math.sin(p / 0.3 * math.pi) : 0.0;                    // one gentle hop, then rest
            return Transform.translate(offset: Offset(0, -b * 3.0), child: child);
          case _ActionMotion.sparkle:
            final tw = s * 0.5 + 0.5;                                                 // 0→1 twinkle
            return Stack(
              clipBehavior: Clip.none,
              alignment: Alignment.center,
              children: [
                child!,
                Positioned(
                  right: -2,
                  top: -2,
                  child: Opacity(
                    opacity: tw,
                    child: Transform.scale(
                      scale: 0.5 + tw * 0.6,
                      child: Icon(Icons.auto_awesome, size: widget.size * 0.5, color: widget.color),
                    ),
                  ),
                ),
              ],
            );
        }
      },
      child: icon,
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

enum _MarkerKind { birthday, income, travel, relationship, crown, celebration, loaned, concern, gentle }

_MarkerKind _kindFor(String e) {
  if (e.contains('🎂')) return _MarkerKind.birthday;
  if (e.contains('👑')) return _MarkerKind.crown;
  if (e.contains('🎉') || e.contains('🎯') || e.contains('🎓') || e.contains('🏁') ||
      e.contains('⭐') || e.contains('💎')) {
    return _MarkerKind.celebration;
  }
  if (e.contains('💸')) return _MarkerKind.loaned;
  if (e.contains('💰') || e.contains('💼') || e.contains('💵')) return _MarkerKind.income;
  if (e.contains('❤') || e.contains('💗') || e.contains('💞') || e.contains('🤝')) return _MarkerKind.relationship;
  if (e.contains('✈')) return _MarkerKind.travel;
  if (e.contains('🔴') || e.contains('🚨')) return _MarkerKind.concern;
  return _MarkerKind.gentle;
}

/// One marked date brought to life. A single lightweight controller drives a
/// subtle, emoji-specific motion — a cake flickers, a coin shimmers, a plane
/// drifts, a heart beats, a crown sparkles — so only meaningful dates move and
/// the calendar never becomes a distracting light show.
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
        double dx = 0, dy = 0, rot = 0, scale = 1, opacity = 1;
        var sparkle = false;
        switch (kind) {
          case _MarkerKind.birthday:
            // candle flicker — quick, irregular opacity + micro-scale jitter
            final f = (math.sin(tau) + math.sin(tau * 2.7) + math.sin(tau * 5.3)) / 3;
            opacity = 0.72 + 0.28 * (f * 0.5 + 0.5);
            scale = 1 + f * 0.05;
          case _MarkerKind.income:
            // coin shimmer — a gentle pulse + sheen of brightness
            scale = 1 + (s * 0.5 + 0.5) * 0.10;
            opacity = 0.82 + 0.18 * (s * 0.5 + 0.5);
          case _MarkerKind.travel:
            dx = s * 2.4;                          // drift left/right
            rot = s * 0.06;
          case _MarkerKind.relationship:
            scale = 1 + (s * 0.5 + 0.5) * 0.20;    // heartbeat
          case _MarkerKind.crown:
            dy = s.abs() * 1.0;
            rot = s * 0.14;                        // gentle tilt
            sparkle = true;                        // + a gold sparkle
          case _MarkerKind.celebration:
            scale = 1 + s * 0.14;                  // confetti pop
            sparkle = true;
          case _MarkerKind.loaned:
            rot = s * 0.22;                        // subtle pendulum swing
          case _MarkerKind.concern:
            scale = 1 + s * 0.05;                  // slow, subdued breathing
          case _MarkerKind.gentle:
            dy = s * 1.0;                          // soft float
        }
        Widget glyph = Opacity(
          opacity: opacity,
          child: Transform.translate(
            offset: Offset(dx, -dy),
            child: Transform.rotate(
              angle: rot,
              child: Transform.scale(scale: scale, child: Text(widget.emoji, style: const TextStyle(fontSize: 11))),
            ),
          ),
        );
        if (sparkle) {
          final tw = math.sin(tau + math.pi / 2) * 0.5 + 0.5; // twinkle out of phase
          glyph = Stack(
            clipBehavior: Clip.none,
            alignment: Alignment.center,
            children: [
              glyph,
              Positioned(
                top: -3,
                right: -3,
                child: Opacity(
                  opacity: tw * 0.9,
                  child: Transform.scale(
                    scale: 0.4 + tw * 0.5,
                    child: const Text('✨', style: TextStyle(fontSize: 8)),
                  ),
                ),
              ),
            ],
          );
        }
        return glyph;
      },
    );
  }
}

/// Today's date with a soft, slow crimson breathing glow — the calendar's
/// always-on sign of life, visible even on a brand-new account with no events.
class _BreathingToday extends StatefulWidget {
  const _BreathingToday({required this.day, required this.color});
  final DateTime day;
  final Color color;

  @override
  State<_BreathingToday> createState() => _BreathingTodayState();
}

class _BreathingTodayState extends State<_BreathingToday> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 2600))..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: AnimatedBuilder(
        animation: _c,
        builder: (context, child) {
          final t = Curves.easeInOut.transform(_c.value);
          return Container(
            width: 34,
            height: 34,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: widget.color.withValues(alpha: 0.16 + 0.10 * t),
              boxShadow: [
                BoxShadow(
                  color: widget.color.withValues(alpha: 0.30 + 0.35 * t),
                  blurRadius: 6 + 10 * t,
                  spreadRadius: 0.5 + 1.5 * t,
                ),
              ],
            ),
            child: child,
          );
        },
        child: Text('${widget.day.day}',
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 13)),
      ),
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
    // Only the budget/income *status* markers need a key — life events show their
    // own emoji (🎂 ✈️ ❤️ …) right on the day, which speaks for itself.
    const items = [
      ('🔴', 'Over budget'),
      ('👑', 'Saved'),
      ('🟢', 'Within budget'),
      ('💼', 'Income'),
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
