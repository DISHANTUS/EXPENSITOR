import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../auth/auth_controller.dart';
import '../auth/auth_state.dart';
import '../../features/auth/login_screen.dart';
import '../../features/home/home_screen.dart';
import '../../features/ledger/add_expense_screen.dart';
import '../../features/ledger/add_hub_screen.dart';
import '../../features/ledger/add_income_screen.dart';
import '../../features/ledger/history_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../features/shell/app_shell.dart';
import '../../features/splash/splash_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  // Bridge Riverpod auth changes -> GoRouter refresh.
  final refresh = ValueNotifier<int>(0);
  ref.listen(authControllerProvider, (_, __) => refresh.value++);
  ref.onDispose(refresh.dispose);

  return GoRouter(
    initialLocation: '/splash',
    refreshListenable: refresh,
    redirect: (context, state) => resolveRedirect(
      status: ref.read(authControllerProvider).status,
      location: state.matchedLocation,
    ),
    routes: [
      GoRoute(path: '/splash', builder: (_, __) => const SplashScreen()),
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      // Authenticated app frame: bottom-nav shell with four branches.
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            AppShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(
            routes: [GoRoute(path: '/home', builder: (_, __) => const HomeScreen())],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/add',
                builder: (_, __) => const AddHubScreen(),
                routes: [
                  GoRoute(path: 'expense', builder: (_, __) => const AddExpenseScreen()),
                  GoRoute(path: 'income', builder: (_, __) => const AddIncomeScreen()),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [GoRoute(path: '/history', builder: (_, __) => const HistoryScreen())],
          ),
          StatefulShellBranch(
            routes: [GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen())],
          ),
        ],
      ),
    ],
  );
});
