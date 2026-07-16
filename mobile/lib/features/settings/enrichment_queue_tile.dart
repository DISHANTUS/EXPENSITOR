import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';

/// How much work is parked for the local model. Counts only — this view has no
/// access to what anyone wrote, by design (see the backend's mail/summary
/// services: it's a queue dashboard, not a window into beta testers' diaries).
class EnrichmentSummary {
  const EnrichmentSummary({
    required this.pending,
    required this.done,
    required this.failed,
    required this.skipped,
    required this.modelAvailable,
    this.oldestPendingAt,
  });

  factory EnrichmentSummary.fromJson(Map<String, dynamic> j) => EnrichmentSummary(
        pending: (j['pending'] as num?)?.toInt() ?? 0,
        done: (j['done'] as num?)?.toInt() ?? 0,
        failed: (j['failed'] as num?)?.toInt() ?? 0,
        skipped: (j['skipped'] as num?)?.toInt() ?? 0,
        modelAvailable: j['model_available'] == true,
        oldestPendingAt: j['oldest_pending_at'] as String?,
      );

  final int pending;
  final int done;
  final int failed;
  final int skipped;
  final bool modelAvailable;
  final String? oldestPendingAt;
}

class EnrichmentRepository {
  EnrichmentRepository(this._dio);
  final Dio _dio;

  Future<EnrichmentSummary> summary() async {
    try {
      final res = await _dio.get<dynamic>('/dev/enrichment');
      return EnrichmentSummary.fromJson(Map<String, dynamic>.from(res.data as Map));
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<Map<String, dynamic>> drain() async {
    try {
      final res = await _dio.post<dynamic>('/dev/enrichment/drain');
      return Map<String, dynamic>.from(res.data as Map);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final enrichmentRepositoryProvider =
    Provider<EnrichmentRepository>((ref) => EnrichmentRepository(ref.watch(dioProvider)));

final enrichmentSummaryProvider =
    FutureProvider.autoDispose<EnrichmentSummary>((ref) => ref.watch(enrichmentRepositoryProvider).summary());

/// Developer-only: shows the model backlog and runs it. The whole point of the
/// catch-up design — turn the model on, tap this, the parked questions get
/// worked out and land in people's diaries.
class EnrichmentQueueTile extends ConsumerStatefulWidget {
  const EnrichmentQueueTile({super.key});

  @override
  ConsumerState<EnrichmentQueueTile> createState() => _EnrichmentQueueTileState();
}

class _EnrichmentQueueTileState extends ConsumerState<EnrichmentQueueTile> {
  bool _draining = false;

  Future<void> _drain() async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _draining = true);
    try {
      final result = await ref.read(enrichmentRepositoryProvider).drain();
      if (!mounted) return;
      setState(() => _draining = false);
      ref.invalidate(enrichmentSummaryProvider);
      // Report what actually happened, including the boring answer: a drain
      // with no model reachable did nothing, and should say so plainly rather
      // than look like success.
      final ran = result['ran'] == true;
      messenger.showSnackBar(SnackBar(
        content: Text(ran
            ? 'Ran ${result['processed']}: ${result['done']} answered, '
                '${result['skipped']} had nothing to add, ${result['failed']} failed. '
                '${result['pending']} still waiting.'
            : 'No model reachable — nothing run. Turn the Ollama bridge on first.'),
      ));
    } catch (e) {
      if (!mounted) return;
      setState(() => _draining = false);
      messenger.showSnackBar(SnackBar(
        content: Text(e is AppError ? e.message : "Couldn't reach the queue"),
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final summary = ref.watch(enrichmentSummaryProvider).valueOrNull;
    final pending = summary?.pending ?? 0;
    final modelUp = summary?.modelAvailable ?? false;

    return Card(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(
            leading: Badge(
              isLabelVisible: pending > 0,
              label: Text('$pending'),
              child: const Icon(Icons.cloud_sync_outlined),
            ),
            title: const Text('Model catch-up queue'),
            subtitle: Text(
              summary == null
                  ? 'Checking…'
                  : pending == 0
                      ? 'Nothing waiting. Model ${modelUp ? "reachable" : "not configured"}.'
                      : '$pending waiting · ${summary.done} answered · ${summary.failed} failed'
                          ' · model ${modelUp ? "reachable" : "not configured"}',
            ),
            trailing: IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: () => ref.invalidate(enrichmentSummaryProvider),
              tooltip: 'Refresh',
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                // Disabled only while a drain is in flight. Still tappable with
                // no model: the backend answers "ran=false" and changes nothing,
                // which is a clearer answer than a greyed-out button.
                onPressed: _draining ? null : _drain,
                icon: _draining
                    ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.play_arrow, size: 18),
                label: Text(_draining ? 'Running…' : 'Drain now'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
