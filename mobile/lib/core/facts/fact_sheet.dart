import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../companion/companion_orb.dart';
import '../theme/app_theme.dart';
import '../theme/glass.dart';
import 'facts_models.dart';
import 'facts_prefs.dart';
import 'facts_repository.dart';

/// A "Did you know?" sheet with Advary's orb, the fact, its category, and a
/// "Tell me another" button. Used by the orb single-tap and the Home card.
Future<void> showFactSheet(BuildContext context, {FactItem? initial}) {
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: Colors.transparent,
    isScrollControlled: true,
    builder: (_) => _FactSheet(initial: initial),
  );
}

class _FactSheet extends ConsumerStatefulWidget {
  const _FactSheet({this.initial});
  final FactItem? initial;

  @override
  ConsumerState<_FactSheet> createState() => _FactSheetState();
}

class _FactSheetState extends ConsumerState<_FactSheet> {
  FactItem? _fact;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _fact = widget.initial;
    if (_fact == null) _another();
  }

  Future<void> _another() async {
    setState(() => _loading = true);
    final disabled = await ref.read(factsPrefsProvider).disabled();
    final fact = await ref.read(factsRepositoryProvider).randomFact(disabled: disabled);
    if (!mounted) return;
    setState(() {
      _fact = fact;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final cs = Theme.of(context).colorScheme;
    final f = _fact;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
        child: GlassCard(
          padding: const EdgeInsets.fromLTRB(16, 18, 16, 14),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const CompanionOrb(state: OrbState.idle, size: 56),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Did you know?',
                            style: tt.labelMedium?.copyWith(
                                color: cs.primary, letterSpacing: 0.4, fontWeight: FontWeight.w700)),
                        const SizedBox(height: 6),
                        if (f != null)
                          Text(f.text, style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w600, height: 1.32))
                        else if (_loading)
                          Text('Thinking of one…', style: tt.bodyMedium?.copyWith(color: cs.onSurfaceVariant))
                        else
                          Text('No facts available yet.', style: tt.bodyMedium?.copyWith(color: cs.onSurfaceVariant)),
                        if (f != null) ...[
                          const SizedBox(height: 8),
                          Text('${f.emoji}  ${f.categoryLabel}',
                              style: tt.labelSmall?.copyWith(color: cs.onSurfaceVariant)),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
                  const Spacer(),
                  FilledButton.tonalIcon(
                    onPressed: _loading ? null : _another,
                    icon: const Icon(Icons.casino_outlined, size: 18),
                    label: const Text('Tell me another'),
                    style: FilledButton.styleFrom(
                        foregroundColor: cs.onSurface, backgroundColor: AppColors.hairline(0.08)),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
