import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/companion/widgets/glow_rail.dart';
import '../../core/theme/app_theme.dart';
import '../../core/timeline/timeline_models.dart';
import '../../core/timeline/timeline_repository.dart';

// Filter chips → the kinds they show (mirrors backend FILTER_GROUPS).
const _filters = ['All', 'Finance', 'Goals', 'Relationships', 'Lessons', 'Achievements', 'Future'];
const _groupKinds = <String, Set<String>?>{
  'All': null,
  'Finance': {'income', 'loan', 'goal'},
  'Goals': {'goal'},
  'Relationships': {'loan', 'event'},
  'Lessons': {'lesson'},
  'Achievements': {'achievement'},
  'Future': null,
};

bool _inGroup(TimelineEntry e, String group) {
  if (group == 'All') return true;
  if (group == 'Future') return e.isFuture;
  if (group == 'Relationships') return e.person != null || {'loan', 'event'}.contains(e.kind);
  final kinds = _groupKinds[group];
  return kinds == null || kinds.contains(e.kind);
}

final _timelineFilterProvider = StateProvider.autoDispose<String>((_) => 'All');
final _timelineQueryProvider = StateProvider.autoDispose<String>((_) => '');

/// The Life Timeline (6a) + filters, search and named chapters (7): the user's
/// money + life story, searchable and filterable.
class TimelineScreen extends ConsumerWidget {
  const TimelineScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(timelineProvider);
    final group = ref.watch(_timelineFilterProvider);
    final query = ref.watch(_timelineQueryProvider);

    return CompanionScaffold(
      title: 'Timeline',
      commentary: async.valueOrNull?.headline ?? 'Let me pull your story together…',
      mood: CompanionMood.happy,
      actions: [
        IconButton(tooltip: 'Add a milestone', icon: const Icon(Icons.add),
            onPressed: () => _showAddMilestone(context, ref)),
        IconButton(tooltip: 'Future Me', icon: const Icon(Icons.auto_graph),
            onPressed: () => context.go('/future-me')),
      ],
      child: Column(
        children: [
          _SearchField(
            onChanged: (q) => ref.read(_timelineQueryProvider.notifier).state = q,
          ),
          if (query.isEmpty) _FilterChips(selected: group,
              onSelect: (g) => ref.read(_timelineFilterProvider.notifier).state = g),
          Expanded(
            child: query.isNotEmpty
                ? _SearchResults(query: query)
                : async.when(
                    loading: () => const Center(child: CircularProgressIndicator()),
                    error: (_, __) => _Retry(onRetry: () => ref.invalidate(timelineProvider)),
                    data: (tl) => _ChaptersView(timeline: tl, group: group,
                        onRefresh: () => ref.invalidate(timelineProvider)),
                  ),
          ),
        ],
      ),
    );
  }
}

class _SearchField extends StatelessWidget {
  const _SearchField({required this.onChanged});
  final ValueChanged<String> onChanged;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
        child: TextField(
          onChanged: onChanged,
          decoration: InputDecoration(
            isDense: true,
            prefixIcon: const Icon(Icons.search),
            hintText: 'Search memories — “involving Ravi”, “June 2026”…',
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(24)),
          ),
        ),
      );
}

class _FilterChips extends StatelessWidget {
  const _FilterChips({required this.selected, required this.onSelect});
  final String selected;
  final ValueChanged<String> onSelect;
  @override
  Widget build(BuildContext context) => SizedBox(
        height: 44,
        child: ListView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          children: [
            for (final f in _filters)
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(label: Text(f), selected: f == selected, onSelected: (_) => onSelect(f)),
              ),
          ],
        ),
      );
}

class _ChaptersView extends StatelessWidget {
  const _ChaptersView({required this.timeline, required this.group, required this.onRefresh});
  final Timeline timeline;
  final String group;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    if (timeline.isEmpty) return const _Empty();
    final children = <Widget>[];
    var idx = 0;
    for (final chapter in timeline.chapters) {
      final shown = chapter.entries.where((e) => _inGroup(e, group)).toList();
      if (shown.isEmpty) continue;
      children.add(_ChapterBanner(label: chapter.label, subtitle: chapter.subtitle));
      for (var i = 0; i < shown.length; i++) {
        children.add(_JourneyEntry(entry: shown[i], index: idx++, last: i == shown.length - 1));
      }
    }
    if (children.isEmpty) {
      children.add(const Padding(padding: EdgeInsets.all(32),
          child: Center(child: Text('Nothing in this filter yet.'))));
    }
    return RefreshIndicator(
      onRefresh: () async => onRefresh(),
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 40), children: children),
    );
  }
}

class _SearchResults extends ConsumerWidget {
  const _SearchResults({required this.query});
  final String query;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(timelineSearchProvider(query));
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (_, __) => const Center(child: Text('Search failed — try again.')),
      data: (res) => ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 40),
        children: [
          Padding(padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(res.summary, style: Theme.of(context).textTheme.titleSmall)),
          for (var i = 0; i < res.entries.length; i++)
            _JourneyEntry(entry: res.entries[i], index: i, last: i == res.entries.length - 1),
        ],
      ),
    );
  }
}

/// Add a non-finance life milestone (move, degree, job…) to the timeline.
Future<void> _showAddMilestone(BuildContext context, WidgetRef ref) async {
  final titleCtrl = TextEditingController();
  var when = DateTime.now();
  var icon = '🌟';
  const icons = ['🌟', '✈️', '🎓', '💼', '🏆', '🏠', '❤️', '🎉'];

  final saved = await showDialog<bool>(
    context: context,
    builder: (ctx) => StatefulBuilder(
      builder: (ctx, setState) => AlertDialog(
        title: const Text('Add a milestone'),
        content: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            TextField(controller: titleCtrl, autofocus: true,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(labelText: 'What’s the milestone?', hintText: 'e.g. Move to Japan')),
            const SizedBox(height: 12),
            Wrap(spacing: 8, children: [
              for (final e in icons)
                GestureDetector(
                  onTap: () => setState(() => icon = e),
                  child: CircleAvatar(
                    backgroundColor: icon == e
                        ? Theme.of(ctx).colorScheme.primaryContainer
                        : Theme.of(ctx).colorScheme.surfaceContainerHighest,
                    child: Text(e),
                  ),
                ),
            ]),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(child: Text('${when.year}-${when.month.toString().padLeft(2, '0')}-${when.day.toString().padLeft(2, '0')}')),
              TextButton(
                onPressed: () async {
                  final picked = await showDatePicker(
                    context: ctx, initialDate: when,
                    firstDate: DateTime(when.year - 5), lastDate: DateTime(when.year + 20));
                  if (picked != null) setState(() => when = picked);
                },
                child: const Text('Pick date'),
              ),
            ]),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
          FilledButton(
            onPressed: titleCtrl.text.trim().isEmpty ? null : () => Navigator.of(ctx).pop(true),
            child: const Text('Add'),
          ),
        ],
      ),
    ),
  );

  if (saved == true && titleCtrl.text.trim().isNotEmpty) {
    final iso = '${when.year}-${when.month.toString().padLeft(2, '0')}-${when.day.toString().padLeft(2, '0')}';
    await ref.read(timelineRepositoryProvider).addLifeEvent(title: titleCtrl.text.trim(), date: iso, icon: icon);
    ref.invalidate(timelineProvider);
  }
}

/// A glowing chapter divider — "━━ STARTING OUT ━━".
class _ChapterBanner extends StatelessWidget {
  const _ChapterBanner({required this.label, this.subtitle = ''});
  final String label;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    Widget line(bool toCenter) => Container(
          height: 1.5,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: toCenter ? Alignment.centerLeft : Alignment.centerRight,
              end: toCenter ? Alignment.centerRight : Alignment.centerLeft,
              colors: [Colors.transparent, AppColors.primary.withValues(alpha: 0.5)],
            ),
          ),
        );
    return Padding(
      padding: const EdgeInsets.only(top: 20, bottom: 12),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(child: line(true)),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Text(
                  label.toUpperCase(),
                  style: tt.titleSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.6,
                    color: AppColors.primary,
                    shadows: [Shadow(color: AppColors.primary.withValues(alpha: 0.6), blurRadius: 12)],
                  ),
                ),
              ),
              Expanded(child: line(false)),
            ],
          ),
          if (subtitle.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(subtitle,
                  textAlign: TextAlign.center,
                  style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant)),
            ),
        ],
      ),
    ).animate().fadeIn(duration: 450.ms).scaleX(begin: 0.85, end: 1, curve: Curves.easeOut);
  }
}

/// One life event on the glowing rail. Milestones glow + shimmer once; future
/// events are dimmer with an "Ahead" tag; people are tappable to their page.
class _JourneyEntry extends StatelessWidget {
  const _JourneyEntry({required this.entry, required this.index, required this.last});
  final TimelineEntry entry;
  final int index;
  final bool last;

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    final color = colorForKind(entry.kind);
    final milestone = entry.isMilestone;
    final future = entry.isFuture;

    final decoration = BoxDecoration(
      borderRadius: BorderRadius.circular(16),
      gradient: milestone
          ? LinearGradient(
              colors: [AppColors.accent.withValues(alpha: 0.30), AppColors.primary.withValues(alpha: 0.12)],
              begin: Alignment.topLeft, end: Alignment.bottomRight)
          : null,
      color: milestone ? null : AppColors.hairline(future ? 0.03 : 0.05),
      border: Border.all(
          color: milestone
              ? AppColors.accent.withValues(alpha: 0.45)
              : AppColors.hairline(future ? 0.12 : 0.08)),
      boxShadow: milestone
          ? [BoxShadow(color: AppColors.accent.withValues(alpha: 0.25), blurRadius: 20, offset: const Offset(0, 8))]
          : null,
    );

    final card = InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: entry.person == null
          ? null
          : () => context.go('/relationship/${Uri.encodeComponent(entry.person!)}'),
      child: Container(
        padding: const EdgeInsets.all(13),
        decoration: decoration,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(entry.title,
                      style: tt.bodyMedium?.copyWith(fontWeight: milestone ? FontWeight.w800 : FontWeight.w600)),
                ),
                if (entry.person != null)
                  Icon(Icons.chevron_right, size: 18, color: cs.onSurfaceVariant),
                if (future)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                        color: AppColors.primary.withValues(alpha: 0.22),
                        borderRadius: BorderRadius.circular(10)),
                    child: Text('Ahead', style: tt.labelSmall),
                  ),
              ],
            ),
            if (entry.detail.isNotEmpty)
              Padding(padding: const EdgeInsets.only(top: 3),
                  child: Text(entry.detail, style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant))),
            if (entry.date != null)
              Padding(padding: const EdgeInsets.only(top: 5),
                  child: Text(entry.date!, style: tt.labelSmall?.copyWith(color: cs.onSurfaceVariant))),
          ],
        ),
      ),
    );

    final row = JourneyRow(
      emoji: entry.icon,
      color: color,
      highlight: milestone,
      dim: future,
      last: last,
      child: card,
    );

    var animated = row
        .animate(delay: (index.clamp(0, 10) * 45).ms)
        .fadeIn(duration: 350.ms)
        .slideY(begin: 0.08, end: 0, curve: Curves.easeOut);
    if (milestone) {
      // A single celebratory sweep across the milestone card (once, on reveal).
      animated = animated.shimmer(
          delay: 250.ms, duration: 1100.ms, color: AppColors.hairline(0.22));
    }
    return animated;
  }
}

class _Empty extends StatelessWidget {
  const _Empty();
  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('📖', style: TextStyle(fontSize: 48)),
            const SizedBox(height: 12),
            Text('Your story starts here.', style: tt.titleMedium, textAlign: TextAlign.center),
            const SizedBox(height: 6),
            Text('Record income, set a goal, or add an event and I’ll remember the chapters.',
                style: tt.bodySmall, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}

class _Retry extends StatelessWidget {
  const _Retry({required this.onRetry});
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('I couldn’t load your timeline.'),
          const SizedBox(height: 8),
          FilledButton.tonal(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}
