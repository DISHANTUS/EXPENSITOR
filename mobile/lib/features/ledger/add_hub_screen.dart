import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// The "Add" tab: choose what to record. Keeps the two flows discoverable
/// without cramming both forms onto one screen.
class AddHubScreen extends StatelessWidget {
  const AddHubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 24, 16, 32),
        children: [
          _AddOption(
            icon: Icons.south_west,
            color: Theme.of(context).colorScheme.error,
            title: 'Add expense',
            subtitle: 'Record money you spent',
            onTap: () => context.go('/add/expense'),
          ),
          const SizedBox(height: 16),
          _AddOption(
            icon: Icons.north_east,
            color: Colors.green.shade700,
            title: 'Add income',
            subtitle: 'Record money you received',
            onTap: () => context.go('/add/income'),
          ),
        ],
      ),
    );
  }
}

class _AddOption extends StatelessWidget {
  const _AddOption({
    required this.icon,
    required this.color,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              CircleAvatar(
                backgroundColor: color.withValues(alpha: 0.15),
                foregroundColor: color,
                child: Icon(icon),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 4),
                    Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}
