import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/format/money.dart';
import 'dashboard_models.dart';
import 'dashboard_repository.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  Future<void> _refresh(WidgetRef ref) async {
    ref.invalidate(proactiveFeedProvider);
    ref.invalidate(dailyBriefProvider);
    ref.invalidate(financialHealthProvider);
    await Future.wait([
      ref.read(proactiveFeedProvider.future).then<void>((_) {}).catchError((_) {}),
      ref.read(dailyBriefProvider.future).then<void>((_) {}).catchError((_) {}),
      ref.read(financialHealthProvider.future).then<void>((_) {}).catchError((_) {}),
    ]);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final health = ref.watch(financialHealthProvider);
    final feed = ref.watch(proactiveFeedProvider);
    final brief = ref.watch(dailyBriefProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Your money, right now'),
      ),
      body: RefreshIndicator(
        onRefresh: () => _refresh(ref),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
          children: [
            _Section(
              title: 'Financial health',
              value: health,
              onRetry: () => ref.invalidate(financialHealthProvider),
              builder: (h) => _HealthCard(h),
            ),
            const SizedBox(height: 16),
            _Section(
              title: 'Most important right now',
              value: feed,
              onRetry: () => ref.invalidate(proactiveFeedProvider),
              builder: (f) => _MostImportantCard(f.mostImportant),
            ),
            const SizedBox(height: 16),
            _Section(
              title: 'Today’s brief',
              value: brief,
              onRetry: () => ref.invalidate(dailyBriefProvider),
              builder: (b) => _BriefCard(b),
            ),
            const SizedBox(height: 16),
            _Section(
              title: 'Recent advisor insights',
              value: feed,
              onRetry: () => ref.invalidate(proactiveFeedProvider),
              builder: (f) => _InsightsList(f.others),
            ),
          ],
        ),
      ),
    );
  }
}

// --- generic async section (title + loading/error/data) --------------------
class _Section<T> extends StatelessWidget {
  const _Section({required this.title, required this.value, required this.builder, required this.onRetry});
  final String title;
  final AsyncValue<T> value;
  final Widget Function(T) builder;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        value.when(
          data: builder,
          loading: () => const _LoadingCard(),
          error: (e, _) => _ErrorCard(message: e is AppError ? e.message : 'Couldn’t load. Pull to refresh.', onRetry: onRetry),
        ),
      ],
    );
  }
}

class _LoadingCard extends StatelessWidget {
  const _LoadingCard();
  @override
  Widget build(BuildContext context) => const Card(
        child: SizedBox(
          height: 96,
          child: Center(child: CircularProgressIndicator()),
        ),
      );
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Icon(Icons.cloud_off, color: Theme.of(context).colorScheme.error),
              const SizedBox(width: 12),
              Expanded(child: Text(message)),
              TextButton(onPressed: onRetry, child: const Text('Retry')),
            ],
          ),
        ),
      );
}

// --- severity helpers -------------------------------------------------------
({IconData icon, Color color}) _severity(BuildContext c, String s) {
  final cs = Theme.of(c).colorScheme;
  switch (s) {
    case 'alert':
      return (icon: Icons.warning_amber_rounded, color: cs.error);
    case 'warning':
      return (icon: Icons.info_outline, color: cs.tertiary);
    case 'success':
      return (icon: Icons.check_circle_outline, color: Colors.green.shade600);
    default:
      return (icon: Icons.lightbulb_outline, color: cs.primary);
  }
}

// --- health card ------------------------------------------------------------
class _HealthCard extends StatelessWidget {
  const _HealthCard(this.h);
  final HealthSummary h;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('${h.overallScore}', style: Theme.of(context).textTheme.displaySmall),
                const Text('/100', style: TextStyle(fontSize: 16)),
                const SizedBox(width: 12),
                Chip(label: Text(h.overallState), visualDensity: VisualDensity.compact),
                if (h.isColdStart) ...[
                  const SizedBox(width: 8),
                  const Chip(label: Text('still learning'), visualDensity: VisualDensity.compact),
                ],
              ],
            ),
            if (!h.isColdStart && h.biggestDrag != null) ...[
              const SizedBox(height: 8),
              Text('Biggest drag: ${h.biggestDrag}', style: TextStyle(color: cs.error)),
            ] else if (!h.isColdStart && h.topStrength != null) ...[
              const SizedBox(height: 8),
              Text(h.topStrength!),
            ] else if (h.isColdStart) ...[
              const SizedBox(height: 8),
              const Text('Add a little spending and income and your health picture sharpens.'),
            ],
            if (h.pillars.isNotEmpty) ...[
              const SizedBox(height: 12),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: h.pillars
                    .map((p) => Chip(
                          label: Text('${p.label} ${p.score}'),
                          visualDensity: VisualDensity.compact,
                          labelStyle: const TextStyle(fontSize: 12),
                        ))
                    .toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

// --- most important card ----------------------------------------------------
class _MostImportantCard extends StatelessWidget {
  const _MostImportantCard(this.item);
  final ProactiveItem? item;

  @override
  Widget build(BuildContext context) {
    if (item == null) {
      return const Card(
        child: ListTile(
          leading: Icon(Icons.verified_outlined),
          title: Text('Nothing needs your attention right now'),
          subtitle: Text('As your activity grows, I’ll surface what matters here.'),
        ),
      );
    }
    final it = item!;
    final sev = _severity(context, it.severity);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(sev.icon, color: sev.color),
                const SizedBox(width: 8),
                Expanded(child: Text(it.title, style: Theme.of(context).textTheme.titleMedium)),
              ],
            ),
            const SizedBox(height: 8),
            Text(it.whatHappened),
            if (it.whyItMatters.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(it.whyItMatters, style: Theme.of(context).textTheme.bodyMedium),
            ],
            if (it.whatNext.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(it.whatNext, style: TextStyle(color: Theme.of(context).colorScheme.primary)),
            ],
            if (it.mostUsefulNumber != null) ...[
              const SizedBox(height: 10),
              Text(it.mostUsefulNumber!, style: const TextStyle(fontWeight: FontWeight.w600)),
            ],
          ],
        ),
      ),
    );
  }
}

// --- daily brief card -------------------------------------------------------
class _BriefCard extends StatelessWidget {
  const _BriefCard(this.b);
  final DailyBrief b;

  @override
  Widget build(BuildContext context) {
    final chips = <Widget>[
      if (b.dailyRemaining != null) _moneyChip('Today', b.dailyRemaining!, b.currency),
      if (b.weeklyRemaining != null) _moneyChip('This week', b.weeklyRemaining!, b.currency),
      if (b.monthlyDiscretionaryRemaining != null) _moneyChip('This month', b.monthlyDiscretionaryRemaining!, b.currency),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (b.headline != null) Text(b.headline!, style: Theme.of(context).textTheme.titleSmall),
            for (final p in b.paragraphs.take(3)) ...[
              const SizedBox(height: 6),
              Text(p),
            ],
            if (chips.isNotEmpty) ...[
              const SizedBox(height: 12),
              Wrap(spacing: 8, runSpacing: 8, children: chips),
            ],
          ],
        ),
      ),
    );
  }

  Widget _moneyChip(String label, String raw, String currency) =>
      Chip(label: Text('$label  ${formatMoney(raw, currency)}'), visualDensity: VisualDensity.compact);
}

// --- recent insights --------------------------------------------------------
class _InsightsList extends StatelessWidget {
  const _InsightsList(this.items);
  final List<ProactiveItem> items;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const Card(
        child: ListTile(
          leading: Icon(Icons.inbox_outlined),
          title: Text('No other insights right now'),
        ),
      );
    }
    return Card(
      child: Column(
        children: [
          for (var i = 0; i < items.length; i++) ...[
            if (i > 0) const Divider(height: 1),
            Builder(builder: (context) {
              final sev = _severity(context, items[i].severity);
              return ListTile(
                leading: Icon(sev.icon, color: sev.color),
                title: Text(items[i].title),
                subtitle: items[i].mostUsefulNumber != null ? Text(items[i].mostUsefulNumber!) : null,
                isThreeLine: false,
              );
            }),
          ],
        ],
      ),
    );
  }
}
