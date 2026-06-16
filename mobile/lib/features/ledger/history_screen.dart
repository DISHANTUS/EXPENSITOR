import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/format/dates.dart';
import '../../core/format/money.dart';
import 'ledger_models.dart';
import 'ledger_repository.dart';

class HistoryScreen extends ConsumerWidget {
  const HistoryScreen({super.key});

  Future<void> _refresh(WidgetRef ref) async {
    ref.invalidate(recentTransactionsProvider);
    await ref.read(recentTransactionsProvider.future).catchError((_) => <Txn>[]);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final txns = ref.watch(recentTransactionsProvider);
    // Best-effort category names; history never blocks on this.
    final categoryNames = {
      for (final c in ref.watch(categoriesProvider).valueOrNull ?? const <CategoryOption>[])
        c.id: c.name,
    };

    return Scaffold(
      appBar: AppBar(title: const Text('History')),
      body: RefreshIndicator(
        onRefresh: () => _refresh(ref),
        child: txns.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _ErrorState(
            message: e is AppError ? e.message : 'Couldn’t load your transactions.',
            onRetry: () => ref.invalidate(recentTransactionsProvider),
          ),
          data: (list) => list.isEmpty
              ? const _EmptyState()
              : ListView.separated(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  itemCount: list.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) => _TxnTile(list[i], categoryNames),
                ),
        ),
      ),
    );
  }
}

class _TxnTile extends StatelessWidget {
  const _TxnTile(this.txn, this.categoryNames);
  final Txn txn;
  final Map<String, String> categoryNames;

  @override
  Widget build(BuildContext context) {
    final credit = txn.isCredit;
    final color = credit ? Colors.green.shade700 : Theme.of(context).colorScheme.error;
    final sign = credit ? '+' : '−';
    final tag = credit ? txn.sourceLabel : (categoryNames[txn.categoryId]);
    final subtitle = [formatDate(txn.date), if (tag != null && tag.isNotEmpty) tag].join(' · ');

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: color.withValues(alpha: 0.15),
        foregroundColor: color,
        child: Icon(credit ? Icons.north_east : Icons.south_west),
      ),
      title: Text(txn.title, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Text(subtitle),
      trailing: Text(
        '$sign${formatMoney(txn.amount, txn.currency)}',
        style: TextStyle(color: color, fontWeight: FontWeight.w600),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();
  @override
  Widget build(BuildContext context) {
    // Must scroll for RefreshIndicator to work over an empty list.
    return ListView(
      children: [
        const SizedBox(height: 120),
        Icon(Icons.receipt_long_outlined,
            size: 64, color: Theme.of(context).colorScheme.outline),
        const SizedBox(height: 16),
        const Center(
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: 32),
            child: Text(
              'No transactions yet.\nTap Add to record your first expense or income.',
              textAlign: TextAlign.center,
            ),
          ),
        ),
      ],
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        const SizedBox(height: 120),
        Icon(Icons.cloud_off, size: 56, color: Theme.of(context).colorScheme.error),
        const SizedBox(height: 16),
        Center(child: Padding(padding: const EdgeInsets.symmetric(horizontal: 32), child: Text(message, textAlign: TextAlign.center))),
        const SizedBox(height: 16),
        Center(child: FilledButton.tonal(onPressed: onRetry, child: const Text('Retry'))),
      ],
    );
  }
}
