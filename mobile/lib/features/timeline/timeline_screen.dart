import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/companion/companion_mood.dart';
import '../../core/companion/companion_scaffold.dart';
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
    for (final chapter in timeline.chapters) {
      final shown = chapter.entries.where((e) => _inGroup(e, group)).toList();
      if (shown.isEmpty) continue;
      children.add(_ChapterHeader(label: chapter.label, subtitle: chapter.subtitle));
      children.addAll(shown.map((e) => _EntryTile(entry: e)));
    }
    if (children.isEmpty) {
      children.add(const Padding(padding: EdgeInsets.all(32),
          child: Center(child: Text('Nothing in this filter yet.'))));
    }
    return RefreshIndicator(
      onRefresh: () async => onRefresh(),
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: children),
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
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          Padding(padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(res.summary, style: Theme.of(context).textTheme.titleSmall)),
          for (final e in res.entries) _EntryTile(entry: e),
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

class _ChapterHeader extends StatelessWidget {
  const _ChapterHeader({required this.label, this.subtitle = ''});
  final String label;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(top: 14, bottom: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text(label, style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w700, color: cs.primary)),
            const SizedBox(width: 10),
            Expanded(child: Divider(color: cs.outlineVariant)),
          ]),
          if (subtitle.isNotEmpty)
            Padding(padding: const EdgeInsets.only(top: 2),
                child: Text(subtitle, style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant))),
        ],
      ),
    );
  }
}

class _EntryTile extends StatelessWidget {
  const _EntryTile({required this.entry});
  final TimelineEntry entry;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    final milestone = entry.isMilestone;
    final future = entry.isFuture;
    final bg = milestone ? cs.tertiaryContainer : (future ? cs.surface : cs.surfaceContainerHighest);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // The rail: an emoji dot + a connecting line.
          Column(
            children: [
              CircleAvatar(radius: 18, backgroundColor: cs.surfaceContainerHighest,
                  child: Text(entry.icon, style: const TextStyle(fontSize: 18))),
              Container(width: 2, height: 26, color: cs.outlineVariant),
            ],
          ),
          const SizedBox(width: 12),
          Expanded(
            child: InkWell(
              borderRadius: BorderRadius.circular(14),
              onTap: entry.person == null ? null
                  : () => context.go('/relationship/${Uri.encodeComponent(entry.person!)}'),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: bg,
                  borderRadius: BorderRadius.circular(14),
                  border: future
                      ? Border.all(color: cs.outline.withValues(alpha: 0.5), style: BorderStyle.solid)
                      : null,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(entry.title,
                              style: tt.bodyMedium?.copyWith(
                                  fontWeight: milestone ? FontWeight.w700 : FontWeight.w500)),
                        ),
                        if (entry.person != null)
                          Icon(Icons.chevron_right, size: 18, color: cs.onSurfaceVariant),
                        if (future)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                                color: cs.primaryContainer, borderRadius: BorderRadius.circular(10)),
                            child: Text('Ahead', style: tt.labelSmall),
                          ),
                      ],
                    ),
                    if (entry.detail.isNotEmpty)
                      Padding(padding: const EdgeInsets.only(top: 2),
                          child: Text(entry.detail, style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant))),
                    if (entry.date != null)
                      Padding(padding: const EdgeInsets.only(top: 4),
                          child: Text(entry.date!, style: tt.labelSmall?.copyWith(color: cs.onSurfaceVariant))),
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
