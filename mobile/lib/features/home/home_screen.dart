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

class _HomeScreenState extends ConsumerState<HomeScreen> with TickerProviderStateMixin {
  DateTime _focused = DateTime.now();
  DateTime? _selected;

  // A single shared ticker gives ONLY event days a gentle float (one controller
  // for the whole grid — cheap, battery-light). Plain days stay perfectly still.
  late final AnimationController _dateAnim =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 3600))..repeat();

  @override
  void dispose() {
    _dateAnim.dispose();
    super.dispose();
  }

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
              selectedDayPredicate: (d) => _selected != null && isSameDay(d, _selected),
              onPageChanged: (f) => setState(() => _focused = f),
              onDaySelected: (selected, focused) {
                // Tap lifts + pops the date (selectedBuilder), then Advary reacts.
                setState(() {
                  _selected = selected;
                  _focused = focused;
                });
                final cell = monthData?.cell(selected);
                if (cell != null && cell.markers.isNotEmpty) {
                  _showDateReaction(context, selected);
                } else {
                  context.go('/date/${ymd(selected)}');
                }
              },
              calendarBuilders: CalendarBuilders(
                // Tasteful, not a casino: plain days stay perfectly still. Only
                // special days move — today breathes, the selected day lifts with a
                // shadow, and days that hold an event gently float.
                defaultBuilder: (context, day, _) {
                  final cell = monthData?.cell(day);
                  final hasEvents = cell != null && cell.markers.isNotEmpty;
                  return _DateCell(
                      day: day, color: cs.onSurface, controller: _dateAnim, float: hasEvents);
                },
                outsideBuilder: (context, day, _) => _DateCell(
                    day: day, color: cs.onSurfaceVariant, controller: _dateAnim, outside: true),
                selectedBuilder: (context, day, _) => _ElevatedDate(day: day, color: cs.primary),
                // Today breathes a soft crimson glow, so the calendar feels alive
                // immediately — no events required.
                todayBuilder: (context, day, _) => _BreathingToday(day: day, color: cs.primary),
                // Living Calendar: only meaningful (marked) dates animate — a crown
                // sparkles, a cake flickers, a plane drifts — everything else still.
                markerBuilder: (context, day, _) {
                  final cell = monthData?.cell(day);
                  if (cell == null || cell.markers.isEmpty) return const SizedBox.shrink();
                  // Resolve keys → registry types (emoji + animation + colour all
                  // come from the backend), highest-priority first.
                  final types = cell.markers
                      .map((k) => registry[k] ?? fallbackMarkers[k])
                      .whereType<CalendarMarkerType>()
                      .where((t) => t.icon.isNotEmpty)
                      .toList()
                    ..sort((a, b) => _markerPriority(a.icon, b.icon));
                  final shown = types.take(3).toList();
                  if (shown.isEmpty) return const SizedBox.shrink();
                  return Padding(
                    padding: const EdgeInsets.only(top: 27),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        for (final t in shown)
                          _LivingMarker(t.icon, animation: t.animation, color: t.color),
                      ],
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

/// The animation a marker plays. Registry-driven: the backend declares the name
/// per event type, so a NEW type animates with zero changes here.
enum _Anim { heartbeat, shimmer, drift, flicker, sparkle, bounce, glow, steam, pulse, swing, warning, float }

_Anim _animFromName(String? name) => switch (name) {
      'heartbeat' => _Anim.heartbeat,
      'shimmer' => _Anim.shimmer,
      'drift' => _Anim.drift,
      'flicker' => _Anim.flicker,
      'sparkle' => _Anim.sparkle,
      'bounce' => _Anim.bounce,
      'glow' => _Anim.glow,
      'steam' => _Anim.steam,
      'pulse' => _Anim.pulse,
      'swing' => _Anim.swing,
      'warning' => _Anim.warning,
      _ => _Anim.float,
    };

/// Fallback when the registry didn't supply an animation (or for the legend):
/// infer a sensible motion straight from the emoji.
_Anim _animFromEmoji(String e) {
  if (e.contains('🎂')) return _Anim.flicker;
  if (e.contains('👑') || e.contains('🎉') || e.contains('🎯') || e.contains('🏁') ||
      e.contains('⭐') || e.contains('💎') || e.contains('🎁')) {
    return _Anim.sparkle;
  }
  if (e.contains('🎓') || e.contains('📚')) return _Anim.bounce;
  if (e.contains('🎮')) return _Anim.glow;
  if (e.contains('🍜') || e.contains('🍔') || e.contains('🍱') || e.contains('☕')) return _Anim.steam;
  if (e.contains('🏥') || e.contains('⚕') || e.contains('💊')) return _Anim.pulse;
  if (e.contains('💸')) return _Anim.swing;
  if (e.contains('💰') || e.contains('💼') || e.contains('💵') || e.contains('🪙')) return _Anim.shimmer;
  if (e.contains('❤') || e.contains('💗') || e.contains('💞') || e.contains('🤝')) return _Anim.heartbeat;
  if (e.contains('✈') || e.contains('🚗') || e.contains('🚆') || e.contains('🚕') || e.contains('🚢')) return _Anim.drift;
  if (e.contains('🔴') || e.contains('🚨') || e.contains('⚠')) return _Anim.warning;
  if (e.contains('🟢')) return _Anim.glow;
  return _Anim.float;
}

/// Default halo colour per animation, used when the registry didn't pass a colour
/// (e.g. the legend). Calendar markers pass the registry colour instead.
Color? _defaultGlow(_Anim a) => switch (a) {
      _Anim.heartbeat => const Color(0xFFFF3B6B),
      _Anim.shimmer => const Color(0xFFFFC247),
      _Anim.sparkle => const Color(0xFFFFC247),
      _Anim.flicker => const Color(0xFFFF9D3B),
      _Anim.glow => const Color(0xFF8B5CFF),
      _Anim.pulse => const Color(0xFFEF5350),
      _Anim.warning => const Color(0xFFE53935),
      _Anim.steam => const Color(0xFFFF8A3D),
      _Anim.bounce => const Color(0xFF26C6DA),
      _ => null, // drift, swing, float — motion only, no halo
    };

/// One marker brought to life. The animation NAME comes from the backend marker
/// registry (registry-driven), with a colour-matched pulsing halo; if the name is
/// absent it's inferred from the emoji. Only meaningful markers move, so the
/// calendar never becomes a distracting light show.
class _LivingMarker extends StatefulWidget {
  const _LivingMarker(this.emoji, {this.animation, this.color, this.size = 11});
  final String emoji;
  final String? animation; // registry-declared name; null → infer from emoji
  final Color? color;      // registry colour for the halo; null → a sensible default
  final double size;

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
    final anim = (widget.animation != null && widget.animation!.isNotEmpty)
        ? _animFromName(widget.animation)
        : _animFromEmoji(widget.emoji);
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) {
        final tau = _c.value * 2 * math.pi;
        final s = math.sin(tau);
        double dx = 0, dy = 0, rot = 0, scale = 1, opacity = 1;
        var sparkle = false, glows = false;
        var glowPulse = s * 0.5 + 0.5; // 0→1
        switch (anim) {
          case _Anim.heartbeat:
            scale = 1 + (s * 0.5 + 0.5) * 0.20;
            glows = true;
          case _Anim.shimmer:
            scale = 1 + (s * 0.5 + 0.5) * 0.10;
            opacity = 0.82 + 0.18 * (s * 0.5 + 0.5);
            glows = true;
          case _Anim.flicker:
            final f = (math.sin(tau) + math.sin(tau * 2.7) + math.sin(tau * 5.3)) / 3;
            opacity = 0.72 + 0.28 * (f * 0.5 + 0.5);
            scale = 1 + f * 0.05;
            glows = true;
            glowPulse = f * 0.5 + 0.5;
          case _Anim.sparkle:
            scale = 1 + s * 0.14;
            sparkle = true;
            glows = true;
          case _Anim.bounce:
            final p = _c.value;
            final b = p < 0.35 ? math.sin(p / 0.35 * math.pi) : 0.0;
            dy = b * 2.6; // one hop, then rest
            glows = true;
            glowPulse = b;
          case _Anim.glow:
            scale = 1 + (s * 0.5 + 0.5) * 0.08;
            glows = true;
          case _Anim.steam:
            dy = (s * 0.5 + 0.5) * 1.6; // a warm rise
            glows = true;
          case _Anim.pulse:
            scale = 1 + (s * 0.5 + 0.5) * 0.12;
            glows = true;
          case _Anim.warning:
            scale = 1 + (s * 0.5 + 0.5) * 0.08;
            glows = true;
          case _Anim.drift:
            dx = s * 2.4;
            rot = s * 0.06;
          case _Anim.swing:
            rot = s * 0.22;
          case _Anim.float:
            dy = s * 1.0;
        }
        final glow = glows ? (widget.color ?? _defaultGlow(anim)) : null;
        Widget glyph = Opacity(
          opacity: opacity,
          child: Transform.translate(
            offset: Offset(dx, -dy),
            child: Transform.rotate(
              angle: rot,
              child: Transform.scale(
                scale: scale,
                child: Text(
                  widget.emoji,
                  style: TextStyle(
                    fontSize: widget.size,
                    shadows: glow == null
                        ? null
                        : [Shadow(color: glow.withValues(alpha: 0.20 + 0.55 * glowPulse), blurRadius: 5 + 11 * glowPulse)],
                  ),
                ),
              ),
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
                    child: Text('✨', style: TextStyle(fontSize: widget.size * 0.6)),
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

/// A calendar day number. Plain days are perfectly still; days that hold an event
/// breathe a gentle vertical float (one shared controller drives them all).
/// Weekends and adjacent-month days read dimmer, matching the default styling.
class _DateCell extends StatelessWidget {
  const _DateCell({
    required this.day,
    required this.color,
    required this.controller,
    this.float = false,
    this.outside = false,
  });
  final DateTime day;
  final Color color;
  final AnimationController controller;
  final bool float;
  final bool outside;

  @override
  Widget build(BuildContext context) {
    final isWeekend = day.weekday == DateTime.saturday || day.weekday == DateTime.sunday;
    final base = outside
        ? color.withValues(alpha: 0.40)
        : (isWeekend ? color.withValues(alpha: 0.62) : color);
    final number = Text('${day.day}',
        style: TextStyle(color: base, fontWeight: FontWeight.w600, fontSize: 15));
    if (!float) return Center(child: number);
    final phase = (day.day % 5) / 5.0; // stagger so event days don't bob in unison
    return Center(
      child: AnimatedBuilder(
        animation: controller,
        builder: (context, child) {
          final t = (controller.value + phase) * 2 * math.pi;
          return Transform.translate(offset: Offset(0, -math.sin(t) * 1.6), child: child);
        },
        child: number,
      ),
    );
  }
}

/// The tapped date: it pops in (easeOutBack) and lifts off the grid with a soft
/// shadow + crimson halo — the "selected" depth cue, paired with the orb reaction.
class _ElevatedDate extends StatelessWidget {
  const _ElevatedDate({required this.day, required this.color});
  final DateTime day;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: 1),
        duration: const Duration(milliseconds: 260),
        curve: Curves.easeOutBack,
        builder: (context, t, child) => Transform.scale(
          scale: 0.9 + 0.22 * t,
          child: Container(
            width: 34,
            height: 34,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color.withValues(alpha: 0.22),
              boxShadow: [
                BoxShadow(color: Colors.black.withValues(alpha: 0.45), blurRadius: 10, offset: const Offset(0, 4)),
                BoxShadow(color: color.withValues(alpha: 0.40), blurRadius: 12, spreadRadius: 0.5),
              ],
            ),
            child: child,
          ),
        ),
        child: Text('${day.day}',
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14)),
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
        runSpacing: 8,
        children: [
          for (final (emoji, label) in items)
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _LivingMarker(emoji, size: 14),
                const SizedBox(width: 5),
                Text(label, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
        ],
      ),
    );
  }
}
