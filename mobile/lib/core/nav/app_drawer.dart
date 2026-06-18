import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../auth/auth_controller.dart';
import '../settings/settings_repository.dart';

class _Dest {
  const _Dest(this.label, this.icon, this.route);
  final String label;
  final IconData icon;
  final String route;
}

const _destinations = <_Dest>[
  _Dest('Home', Icons.calendar_month, '/home'),
  _Dest('Budget Setup', Icons.account_balance_wallet_outlined, '/budget-setup'),
  _Dest('Plan Today', Icons.today_outlined, '/plan-today'),
  _Dest('Timeline', Icons.timeline, '/timeline'),
  _Dest('Future Me', Icons.auto_graph, '/future-me'),
  _Dest('People', Icons.people_outline, '/relationships'),
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
    final email = ref.watch(authControllerProvider).user?.email;
    final companion = ref.watch(userSettingsProvider).valueOrNull?.companionName;

    return Drawer(
      child: SafeArea(
        child: Column(
          children: [
            DrawerHeader(
              decoration: BoxDecoration(color: cs.primaryContainer),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  const Text('🙂', style: TextStyle(fontSize: 32)),
                  const SizedBox(height: 8),
                  Text((companion == null || companion.isEmpty) ? 'Advary' : companion,
                      style: Theme.of(context).textTheme.titleLarge),
                  Text('your companion', style: Theme.of(context).textTheme.labelSmall),
                  if (email != null)
                    Text(email, style: Theme.of(context).textTheme.bodySmall, overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
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
