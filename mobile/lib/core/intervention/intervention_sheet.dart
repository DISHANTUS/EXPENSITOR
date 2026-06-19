import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../analytics/analytics.dart';
import '../companion/companion_orb.dart';
import '../theme/glass.dart';
import 'intervention.dart';
import 'intervention_controller.dart';

/// The reusable "Advary wants to talk" sheet — the single conversation surface
/// for EVERY intervention. Stage 1 is the gentle opener; Stage 2 shows the
/// message and either asks a question (an answer mints a [Fact]) or offers an
/// action. Debt, event-impact and income-verification all reuse this verbatim.
void showInterventionSheet(BuildContext context) {
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: Colors.transparent,
    builder: (_) => const _InterventionSheet(),
  );
}

class _InterventionSheet extends ConsumerStatefulWidget {
  const _InterventionSheet();
  @override
  ConsumerState<_InterventionSheet> createState() => _InterventionSheetState();
}

class _InterventionSheetState extends ConsumerState<_InterventionSheet> {
  bool _talking = false;

  void _resolveAndClose(Intervention i, {Fact? fact, String? route}) {
    ref.read(interventionControllerProvider.notifier).resolve(i.id, fact: fact);
    Navigator.of(context).pop();
    if (route != null) context.go(route);
  }

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    final top = ref.watch(topInterventionProvider);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
        child: GlassCard(
          padding: const EdgeInsets.fromLTRB(16, 18, 16, 16),
          child: top == null
              ? Row(children: [
                  const CompanionOrb(state: OrbState.celebrating, size: 56),
                  const SizedBox(width: 12),
                  Expanded(child: Text('All caught up — nothing needs your attention right now.',
                      style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w600))),
                ])
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        CompanionOrb(
                            state: top.priority == InterventionPriority.urgent
                                ? OrbState.concerned
                                : OrbState.idle,
                            size: 56),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: _talking
                                ? Text(top.title,
                                    style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w700, height: 1.25))
                                : Text('Advary wants to talk',
                                    style: tt.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    if (!_talking) ...[
                      Text('I noticed something that might be worth a look.',
                          style: tt.bodyMedium?.copyWith(height: 1.35)),
                      const SizedBox(height: 16),
                      Row(children: [
                        Expanded(
                          child: FilledButton(
                            onPressed: () => setState(() => _talking = true),
                            child: const Text("Let's talk"),
                          ),
                        ),
                        const SizedBox(width: 10),
                        TextButton(
                          onPressed: () {
                            ref.read(analyticsProvider).track('intervention_dismissed',
                                {'trigger': top.trigger.name, 'stage': 'opener'});
                            Navigator.of(context).pop();
                          },
                          child: const Text('Later'),
                        ),
                      ]),
                    ] else ...[
                      Text(top.message, style: tt.bodyMedium?.copyWith(height: 1.4)),
                      const SizedBox(height: 16),
                      if (top.question != null && top.choices.isNotEmpty) ...[
                        Text(top.question!, style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 8),
                        for (final c in top.choices)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: SizedBox(
                              width: double.infinity,
                              child: OutlinedButton(
                                onPressed: () => _resolveAndClose(top, fact: c.fact),
                                style: OutlinedButton.styleFrom(
                                    foregroundColor: cs.onSurface, alignment: Alignment.centerLeft),
                                child: Text(c.label),
                              ),
                            ),
                          ),
                      ] else ...[
                        Row(children: [
                          if (top.actionLabel != null)
                            Expanded(
                              child: FilledButton(
                                onPressed: () => _resolveAndClose(top, route: top.actionRoute),
                                child: Text(top.actionLabel!),
                              ),
                            ),
                          if (top.actionLabel != null) const SizedBox(width: 10),
                          TextButton(
                            onPressed: () {
                              ref.read(analyticsProvider).track('intervention_dismissed',
                                  {'trigger': top.trigger.name, 'stage': 'message'});
                              _resolveAndClose(top);
                            },
                            child: const Text('Got it'),
                          ),
                        ]),
                      ],
                    ],
                  ],
                ),
        ),
      ),
    );
  }
}
