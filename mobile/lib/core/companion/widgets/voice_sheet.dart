import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../onboarding/tour_controller.dart';
import '../../voice/conversation_controller.dart';

const _navRoutes = {'future-me': '/future-me', 'report': '/timeline', 'plan-today': '/plan-today'};

/// Resolve a voice `navigate` hint to a route: the legacy short names, or any
/// full path the backend sends directly (how-to answers send e.g. "/budget-setup").
String? _resolveRoute(String? navigate) {
  if (navigate == null) return null;
  return _navRoutes[navigate] ?? (navigate.startsWith('/') ? navigate : null);
}

/// Open the conversation sheet and start listening; stop the loop when dismissed.
Future<void> showVoiceSheet(BuildContext context, WidgetRef ref) async {
  ref.read(conversationControllerProvider.notifier).open();
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => const VoiceSheet(),
  );
  await ref.read(conversationControllerProvider.notifier).close();
}

/// The lightweight "talk to the companion" sheet: a status line, the live
/// transcript, the spoken reply, and a mic/stop control.
class VoiceSheet extends ConsumerWidget {
  const VoiceSheet({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(conversationControllerProvider);
    final n = ref.read(conversationControllerProvider.notifier);
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;

    // "Show me around" by voice launches the tour — close this sheet so the
    // walkthrough overlay isn't stacked behind it.
    ref.listen<bool>(tourControllerProvider.select((t) => t.active), (_, active) {
      if (active) Navigator.of(context).maybePop();
    });

    final navRoute = _resolveRoute(s.navigate);

    final label = switch (s.phase) {
      ConvPhase.listening => 'Listening…',
      ConvPhase.thinking => 'Thinking…',
      ConvPhase.speaking => 'Speaking…',
      ConvPhase.unavailable => 'Voice input isn’t available',
      ConvPhase.error => 'Something went wrong',
      ConvPhase.idle => 'Tap the mic to talk',
    };
    final busy = s.phase == ConvPhase.listening || s.phase == ConvPhase.thinking || s.phase == ConvPhase.speaking;

    return Padding(
      padding: EdgeInsets.fromLTRB(16, 4, 16, 16 + MediaQuery.of(context).viewInsets.bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              SizedBox(
                width: 22, height: 22,
                child: busy
                    ? CircularProgressIndicator(strokeWidth: 2.5, color: cs.primary)
                    : Icon(Icons.graphic_eq, color: cs.primary),
              ),
              const SizedBox(width: 12),
              Text(label, style: tt.titleMedium),
            ],
          ),
          const SizedBox(height: 16),
          if (s.transcript.isNotEmpty)
            Align(
              alignment: Alignment.centerRight,
              child: _Bubble(text: s.transcript, color: cs.primaryContainer, align: TextAlign.right),
            ),
          if (s.reply.isNotEmpty) ...[
            const SizedBox(height: 8),
            _Bubble(text: s.reply, color: cs.surfaceContainerHighest, align: TextAlign.left),
          ],
          if (s.transcript.isEmpty && s.reply.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text('Try: “show my red days”, “report for last month”, “show me Future Me”',
                  style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant)),
            ),
          if (navRoute != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Align(
                alignment: Alignment.centerLeft,
                child: FilledButton.tonalIcon(
                  icon: const Icon(Icons.open_in_new),
                  label: Text(s.navigate == 'future-me' ? 'Open Future Me' : 'Show me'),
                  onPressed: () {
                    Navigator.of(context).maybePop();
                    context.go(navRoute);
                  },
                ),
              ),
            ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (s.phase == ConvPhase.listening || s.phase == ConvPhase.speaking)
                FilledButton.tonalIcon(
                  onPressed: n.stop,
                  icon: const Icon(Icons.stop), label: const Text('Stop'),
                )
              else
                FilledButton.icon(
                  onPressed: s.phase == ConvPhase.unavailable ? null : n.listenAgain,
                  icon: const Icon(Icons.mic), label: const Text('Speak'),
                ),
              const SizedBox(width: 12),
              TextButton(onPressed: () => Navigator.of(context).maybePop(), child: const Text('Done')),
            ],
          ),
        ],
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.text, required this.color, required this.align});
  final String text;
  final Color color;
  final TextAlign align;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 460),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(14)),
      child: Text(text, textAlign: align, style: Theme.of(context).textTheme.bodyMedium),
    );
  }
}
