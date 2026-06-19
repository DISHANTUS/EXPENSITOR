import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/format/dates.dart';
import '../../core/theme/glass.dart';

/// A discoverable "add to your calendar" entry for real users — pick a date and
/// what happened, and it opens the right add screen (which feeds the Living
/// Calendar, Timeline, People, Journey and Future Me). Built on the existing
/// per-date add flows.
Future<void> showAddEventSheet(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: Colors.transparent,
    isScrollControlled: true,
    builder: (_) => const _AddEventSheet(),
  );
}

// (emoji, label, helper, route segment under /date/:date/)
const _types = <(String, String, String, String)>[
  ('🎂', 'Plan an event', 'Birthday · outing · trip · exam…', 'add-event'),
  ('💰', 'Income received', 'Salary · scholarship · gift', 'add-income'),
  ('💸', 'Log an expense', 'Something you spent', 'add-expense'),
  ('🤝', 'Lent money', 'Track who owes you back', 'add-lent'),
  ('🪙', 'Borrowed money', "Money you owe — I'll help you repay it", 'add-borrowed'),
];

class _AddEventSheet extends StatefulWidget {
  const _AddEventSheet();
  @override
  State<_AddEventSheet> createState() => _AddEventSheetState();
}

class _AddEventSheetState extends State<_AddEventSheet> {
  DateTime _date = DateTime.now();

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(now.year - 5),
      lastDate: DateTime(now.year + 6),
    );
    if (picked != null) setState(() => _date = picked);
  }

  void _open(String segment) {
    Navigator.of(context).pop();
    context.go('/date/${ymd(_date)}/$segment');
  }

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
        child: GlassCard(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 10),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Add to your calendar', style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: 10),
              Row(children: [
                Icon(Icons.event_outlined, size: 18, color: cs.onSurfaceVariant),
                const SizedBox(width: 8),
                Expanded(child: Text(formatDate(_date), style: tt.bodyMedium)),
                TextButton(onPressed: _pickDate, child: const Text('Change date')),
              ]),
              const Divider(height: 16),
              for (final (emoji, label, helper, segment) in _types)
                ListTile(
                  contentPadding: const EdgeInsets.symmetric(horizontal: 4),
                  leading: Text(emoji, style: const TextStyle(fontSize: 22)),
                  title: Text(label, style: tt.bodyLarge?.copyWith(fontWeight: FontWeight.w600)),
                  subtitle: Text(helper, style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant)),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _open(segment),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
