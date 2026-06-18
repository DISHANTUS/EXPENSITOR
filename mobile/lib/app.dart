import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/onboarding/companion_tour.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';

class ExpensitorApp extends ConsumerWidget {
  const ExpensitorApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: 'Expensitor',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark(),
      darkTheme: AppTheme.dark(),
      themeMode: ThemeMode.dark,
      routerConfig: router,
      // The first-launch guided tour sits above every screen and navigates the
      // real app while Advary narrates.
      builder: (context, child) => TourHost(child: child ?? const SizedBox.shrink()),
    );
  }
}
