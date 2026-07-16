import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../auth/auth_controller.dart';
import '../auth/auth_state.dart';
import '../voice/conversation_controller.dart';
import '../voice/voice_service.dart';
import '../../features/advisor/chat_screen.dart';
import '../../features/appearance/appearance_screen.dart';
import '../../features/auth/login_screen.dart';
import '../../features/budget_setup/budget_setup_screen.dart';
import '../../features/budget_setup/plan_screen.dart';
import '../../features/budget_setup/profile_summary_screen.dart';
import '../../features/feedback/feedback_screen.dart';
import '../../features/contact/contact_screen.dart';
import '../../features/convert/currency_center_screen.dart';
import '../../features/date_details/date_details_screen.dart';
import '../../features/home/home_screen.dart';
import '../../features/journey/journey_screen.dart';
import '../../features/ledger/add_borrowed_screen.dart';
import '../../features/ledger/add_event_screen.dart';
import '../../features/ledger/add_expense_screen.dart';
import '../../features/ledger/add_income_screen.dart';
import '../../features/ledger/add_lent_screen.dart';
import '../../features/payables/repayment_plan_screen.dart';
import '../../features/plan_today/plan_today_screen.dart';
import '../../features/settings/settings_screen.dart';
import '../../features/future_me/future_me_screen.dart';
import '../../features/relationships/relationship_detail_screen.dart';
import '../../features/relationships/relationships_screen.dart';
import '../../features/splash/splash_screen.dart';
import '../../features/timeline/timeline_screen.dart';
import '../../features/voice_studio/voice_studio_screen.dart';

DateTime _parseDate(GoRouterState state) =>
    DateTime.tryParse(state.pathParameters['date'] ?? '') ?? DateTime.now();

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier<int>(0);
  ref.listen(authControllerProvider, (_, __) => refresh.value++);
  ref.onDispose(refresh.dispose);

  return GoRouter(
    initialLocation: '/splash',
    refreshListenable: refresh,
    observers: [_VoiceStopObserver(ref)],   // interruption: stop speech on navigation
    redirect: (context, state) => resolveRedirect(
      status: ref.read(authControllerProvider).status,
      location: state.matchedLocation,
    ),
    routes: [
      GoRoute(path: '/splash', builder: (_, __) => const SplashScreen()),
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
      GoRoute(path: '/plan-today', builder: (_, __) => const PlanTodayScreen()),
      GoRoute(path: '/contact', builder: (_, __) => const ContactScreen()),
      GoRoute(path: '/settings', builder: (_, __) => const SettingsScreen()),
      GoRoute(path: '/voice-studio', builder: (_, __) => const VoiceStudioScreen()),
      GoRoute(path: '/appearance', builder: (_, __) => const AppearanceScreen()),
      GoRoute(path: '/convert', builder: (_, __) => const CurrencyCenterScreen()),
      GoRoute(path: '/budget-setup', builder: (_, __) => const BudgetSetupScreen()),
      GoRoute(path: '/plan', builder: (_, __) => const PlanScreen()),
      GoRoute(path: '/profile-summary', builder: (_, __) => const ProfileSummaryScreen()),
      // ?ask= pre-fills the composer, so text typed on another screen (Planning)
      // travels with the user instead of having to be retyped.
      GoRoute(
        path: '/advisor',
        builder: (_, state) => ChatScreen(initialText: state.uri.queryParameters['ask']),
      ),
      GoRoute(path: '/timeline', builder: (_, __) => const TimelineScreen()),
      GoRoute(path: '/future-me', builder: (_, __) => const FutureMeScreen()),
      GoRoute(path: '/relationships', builder: (_, __) => const RelationshipsScreen()),
      GoRoute(path: '/journey', builder: (_, __) => const JourneyScreen()),
      GoRoute(path: '/relationship/:name',
          builder: (_, state) => RelationshipDetailScreen(name: state.pathParameters['name'] ?? '')),
      GoRoute(path: '/feedback', builder: (_, __) => const FeedbackScreen()),
      GoRoute(
        path: '/payable/:id/repay',
        builder: (_, state) => RepaymentPlanScreen(payableId: state.pathParameters['id'] ?? ''),
      ),
      GoRoute(
        path: '/date/:date',
        builder: (_, state) => DateDetailsScreen(date: _parseDate(state)),
        routes: [
          GoRoute(path: 'add-expense', builder: (_, state) => AddExpenseScreen(date: _parseDate(state))),
          GoRoute(path: 'add-income', builder: (_, state) => AddIncomeScreen(date: _parseDate(state))),
          GoRoute(path: 'add-event', builder: (_, state) => AddEventScreen(date: _parseDate(state))),
          GoRoute(path: 'add-lent', builder: (_, state) => AddLentScreen(date: _parseDate(state))),
          GoRoute(path: 'add-borrowed', builder: (_, state) => AddBorrowedScreen(date: _parseDate(state))),
        ],
      ),
    ],
  );
});

/// Stops any in-progress companion speech whenever the user navigates — voice is
/// always interruptible (Sprint 5a).
class _VoiceStopObserver extends NavigatorObserver {
  _VoiceStopObserver(this._ref);
  final Ref _ref;

  void _stop() {
    // Release BOTH the speaker (TTS) and the mic (STT) on navigation. A live mic
    // session leaves Android in "communication mode", which silences the user's
    // ringtones and notification sounds until the session is closed.
    try {
      _ref.read(voiceControllerProvider.notifier).stop();
    } catch (_) {/* voice not initialised yet */}
    try {
      _ref.read(conversationControllerProvider.notifier).stop();
    } catch (_) {/* conversation not initialised yet */}
  }

  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) => _stop();
  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) => _stop();
  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) => _stop();
}
