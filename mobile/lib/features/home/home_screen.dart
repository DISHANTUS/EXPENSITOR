import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:table_calendar/table_calendar.dart';

import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/companion/greeting.dart';
import '../../core/format/dates.dart';
import '../calendar/calendar_models.dart';
import '../calendar/calendar_repository.dart';
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

    return CompanionScaffold(
      title: 'Home',
      // Home is the ONLY screen with the live daily companion greeting + mood
      // rotation; timeGreeting() is the fallback before the live one loads.
      showGreeting: true,
      commentary: timeGreeting(),
      mood: moodFromSeverity(brief.valueOrNull?.severity),
      child: ListView(
        children: [
          _QuickCards(),
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
                onDaySelected: (selected, _) => context.go('/date/${ymd(selected)}'),
                calendarBuilders: CalendarBuilders(
                  markerBuilder: (context, day, _) {
                    final cell = monthData?.cell(day);
                    if (cell == null || cell.markers.isEmpty) return const SizedBox.shrink();
                    return Padding(
                      padding: const EdgeInsets.only(top: 28),
                      child: Text(
                        cell.markers
                            .take(3)
                            .map((k) => (registry[k] ?? fallbackMarkers[k])?.icon ?? '')
                            .join(),
                        style: const TextStyle(fontSize: 9),
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
        ],
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

const _quick = <_QuickCard>[
  _QuickCard('Plan Today', Icons.today_outlined, '/plan-today'),
  _QuickCard('Budget Setup', Icons.account_balance_wallet_outlined, '/budget-setup'),
  _QuickCard('Timeline', Icons.timeline, '/timeline'),
  _QuickCard('Future Me', Icons.auto_graph, '/future-me'),
  _QuickCard('Advisor', Icons.chat_bubble_outline, '/advisor'),
  _QuickCard('Convert', Icons.currency_exchange, '/convert'),
];

class _QuickCards extends StatelessWidget {
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
