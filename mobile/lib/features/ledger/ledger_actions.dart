import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/companion/reaction.dart';
import '../../core/companion/reaction_queue.dart';
import '../calendar/calendar_repository.dart';
import '../home/daily_report_repository.dart';
import '../home/dashboard_repository.dart';
import 'ledger_repository.dart';

/// Re-fetch everything a new expense/income/event affects: the dashboard
/// commentary, the calendar month grid, every day-detail view, and today's
/// report (which counts the money that just moved).
void refreshAfterWrite(WidgetRef ref) {
  ref.invalidate(dailyBriefProvider);
  ref.invalidate(financialHealthProvider);
  ref.invalidate(proactiveFeedProvider);
  ref.invalidate(recentTransactionsProvider);
  ref.invalidate(monthViewProvider);
  ref.invalidate(dayDetailProvider);
  ref.invalidate(dailyReportProvider);
}

/// Success flow shared by the add forms: refresh, push a companion reaction
/// (shown over the greeting), and return to Home.
void completeLedgerWrite(BuildContext context, WidgetRef ref, {required String kind, String? goalLabel}) {
  refreshAfterWrite(ref);
  ref.read(reactionQueueProvider.notifier).push(reactionFor(kind, label: goalLabel));
  context.go('/home');
}
