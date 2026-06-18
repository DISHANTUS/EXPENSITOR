import 'package:flutter/material.dart';

import '../../core/companion/companion_scaffold.dart';

/// Honest "coming soon" screen so the Drawer/quick-card destinations are wired
/// now; each is replaced by its real feature in Sprint 4/5.
class PlaceholderScreen extends StatelessWidget {
  const PlaceholderScreen({
    super.key,
    required this.title,
    required this.message,
    required this.icon,
    this.commentary,
  });

  final String title;
  final String message;
  final IconData icon;
  final String? commentary;

  @override
  Widget build(BuildContext context) {
    return CompanionScaffold(
      title: title,
      commentary: commentary ?? '$title is on the way.',
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 64, color: Theme.of(context).colorScheme.outline),
              const SizedBox(height: 16),
              Text(message, textAlign: TextAlign.center),
            ],
          ),
        ),
      ),
    );
  }
}
