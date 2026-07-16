import 'package:flutter/material.dart';

import '../chat_models.dart';

/// Learning-loop check-in (4b-5a): the companion asks "what happened?" about a
/// past piece of advice. `choice` questions (Yes/Partially/No) record a
/// Phase-E Outcome directly; `free_text` questions (spending_shift) take a
/// short typed reason instead — see advice_memory_service.answer.
class FollowUpCard extends StatefulWidget {
  const FollowUpCard(this.q, {super.key, required this.onAnswer, this.answered});
  final FollowUpQuestion q;

  /// Returns null when the answer landed, or a short message to show inline —
  /// either a "say a little more" nudge (a reason judged too thin) or an
  /// error. The typed reason is cleared ONLY on success, so a failed send
  /// never silently eats what the user wrote.
  final Future<String?> Function(String value, {String? detail}) onAnswer;
  final String? answered;   // ack text once answered (disables chips/input)

  @override
  State<FollowUpCard> createState() => _FollowUpCardState();
}

class _FollowUpCardState extends State<FollowUpCard> {
  final _controller = TextEditingController();
  bool _sending = false;
  String? _notice;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _sending) return;
    setState(() {
      _sending = true;
      _notice = null;
    });
    final notice = await widget.onAnswer('explained', detail: text);
    if (!mounted) return;
    setState(() {
      _sending = false;
      _notice = notice;
      if (notice == null) _controller.clear();
    });
  }

  Future<void> _choose(String value) async {
    if (_sending) return;
    setState(() => _sending = true);
    final notice = await widget.onAnswer(value);
    if (!mounted) return;
    setState(() {
      _sending = false;
      _notice = notice;
    });
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    final q = widget.q;
    final freeText = q.responseType == 'free_text';
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      color: cs.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.history_outlined, size: 18, color: cs.primary),
              const SizedBox(width: 6),
              const Text('Quick check-in', style: TextStyle(fontWeight: FontWeight.w600)),
            ]),
            const SizedBox(height: 8),
            Text(q.question),
            const SizedBox(height: 10),
            if (widget.answered != null)
              Row(children: [
                Icon(Icons.check_circle_outline, size: 16, color: cs.primary),
                const SizedBox(width: 6),
                Expanded(child: Text(widget.answered!, style: tt.bodyMedium)),
              ])
            else if (freeText)
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  TextField(
                    controller: _controller,
                    enabled: !_sending,
                    minLines: 1,
                    maxLines: 3,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _submit(),
                    decoration: const InputDecoration(
                      hintText: "What's changed?",
                      isDense: true,
                      border: OutlineInputBorder(),
                    ),
                  ),
                  if (_notice != null) ...[
                    const SizedBox(height: 6),
                    Text(_notice!, style: tt.bodySmall?.copyWith(color: cs.primary)),
                  ],
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton(
                      onPressed: _sending ? null : _submit,
                      child: _sending
                          ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Text('Send'),
                    ),
                  ),
                ],
              )
            else
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(spacing: 8, runSpacing: 8, children: [
                    for (final o in q.options)
                      ActionChip(label: Text(o.label), onPressed: _sending ? null : () => _choose(o.value)),
                  ]),
                  if (_notice != null) ...[
                    const SizedBox(height: 6),
                    Text(_notice!, style: tt.bodySmall?.copyWith(color: cs.primary)),
                  ],
                ],
              ),
          ],
        ),
      ),
    );
  }
}
