import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../home/dashboard_repository.dart';
import 'ledger_repository.dart';

/// Re-fetch everything a new expense/income affects.
void refreshDashboardAndHistory(WidgetRef ref) {
  ref.invalidate(financialHealthProvider);
  ref.invalidate(proactiveFeedProvider);
  ref.invalidate(dailyBriefProvider);
  ref.invalidate(recentTransactionsProvider);
}

/// Success flow shared by both forms: refresh the dashboard + history, confirm
/// with a snackbar, and return to Home. The messenger is captured before
/// navigating so the snackbar survives the route change.
void completeLedgerWrite(BuildContext context, WidgetRef ref, String message) {
  final messenger = ScaffoldMessenger.of(context);
  refreshDashboardAndHistory(ref);
  messenger.showSnackBar(SnackBar(content: Text(message)));
  context.go('/home');
}
