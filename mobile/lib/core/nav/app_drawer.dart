import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../auth/auth_controller.dart';
import '../companion/companion_orb.dart';
import '../home/day_state.dart';
import '../settings/settings_repository.dart';
import '../theme/app_theme.dart';

/// A small, alive line under the companion name. Uses the user's chosen name
/// (never their email) when they've told us one.
String _greeting(int hour, String? name) {
  final part = hour < 12 ? 'Good morning' : (hour < 17 ? 'Good afternoon' : 'Good evening');
  return name == null || name.isEmpty ? 'your personal companion' : '$part, $name.';
}

class _Dest {
  const _Dest(this.label, this.icon, this.route);
  final String label;
  final IconData icon;
  final String route;
}

const _destinations = <_Dest>[
  _Dest('Home', Icons.calendar_month, '/home'),
  _Dest('Budget Setup', Icons.account_balance_wallet_outlined, '/budget-setup'),
  _Dest('Your Plan', Icons.insights_outlined, '/plan'),
  _Dest('Plan Today', Icons.today_outlined, '/plan-today'),
  _Dest('Timeline', Icons.timeline, '/timeline'),
  _Dest('Future Me', Icons.auto_graph, '/future-me'),
  _Dest('People', Icons.people_outline, '/relationships'),
  _Dest('Your Journey', Icons.auto_awesome_outlined, '/journey'),
  _Dest('Chat With Advisor', Icons.chat_bubble_outline, '/advisor'),
  _Dest('Currency Converter', Icons.currency_exchange, '/convert'),
  _Dest('Settings', Icons.settings_outlined, '/settings'),
  _Dest('Feedback', Icons.feedback_outlined, '/feedback'),
  _Dest('Contact Us', Icons.contact_support_outlined, '/contact'),
];

/// Primary navigation. The same destinations also appear as quick-access cards
/// on Home; this is the secondary entry point.
class AppDrawer extends ConsumerWidget {
  const AppDrawer({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final current = GoRouterState.of(context).matchedLocation;
    final settings = ref.watch(userSettingsProvider).valueOrNull;
    final companion = (settings?.companionName?.isNotEmpty ?? false) ? settings!.companionName! : 'Advary';
    final name = settings?.displayName;

    return Drawer(
      backgroundColor: AppColors.surface,
      child: SafeArea(
        child: Column(
          children: [
            // Integrated aurora header (no solid block): the orb + identity sit on
            // a soft gradient that bleeds to the drawer edges, matching Home's glass look.
            Container(
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(20, 22, 20, 18),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    AppColors.primary.withValues(alpha: 0.22),
                    AppColors.secondary.withValues(alpha: 0.06),
                    Colors.transparent,
                  ],
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const CompanionOrb(state: OrbState.idle, size: 52),
                  const SizedBox(height: 10),
                  Text(companion,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                  const SizedBox(height: 2),
                  Text(_greeting(DateTime.now().hour, name),
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: cs.onSurfaceVariant)),
                ],
              ),
            ),
            Divider(height: 1, color: AppColors.hairline(0.08)),
            Expanded(
              child: ListView(
                padding: EdgeInsets.zero,
                children: [
                  for (final d in _destinations)
                    ListTile(
                      leading: Icon(d.icon),
                      title: Text(d.label),
                      selected: current == d.route,
                      onTap: () {
                        Navigator.of(context).pop();
                        // Home's drawer entry is always "show me the calendar" —
                        // even mid-compact-view, even if already on /home.
                        if (d.route == '/home') {
                          ref.read(homeDayStateProvider.notifier).forceFull();
                        }
                        if (current != d.route) context.go(d.route);
                      },
                    ),
                ],
              ),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.logout),
              title: const Text('Log out'),
              onTap: () {
                Navigator.of(context).pop();
                ref.read(authControllerProvider.notifier).logout();
              },
            ),
          ],
        ),
      ),
    );
  }
}
