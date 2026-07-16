import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api/api_exception.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/companion/companion_mood.dart';
import '../../core/format/dates.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/glass.dart';
import 'diary_repository.dart';

/// Your diary — write what happened, and Advary asks about whatever you left
/// vague. Over time it counts what you keep writing about and tells you.
///
/// This is a private diary. What's here is used to make YOUR experience better,
/// in your app, on your account — the patterns are yours, told back to you.
class DiaryScreen extends ConsumerWidget {
  const DiaryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return const CompanionScaffold(
      title: 'Diary',
      commentary: "Tell me about your day. I'll ask if something's not clear — "
          "and over time I'll start noticing what keeps coming up.",
      mood: CompanionMood.happy,
      child: DiaryBody(),
    );
  }
}

/// Public so widget tests can mount the diary itself without dragging the whole
/// companion scaffold (orb, mood, greeting) in behind it.
class DiaryBody extends ConsumerStatefulWidget {
  const DiaryBody({super.key});
  @override
  ConsumerState<DiaryBody> createState() => _DiaryBodyState();
}

class _DiaryBodyState extends ConsumerState<DiaryBody> {
  final _note = TextEditingController();
  final _reply = TextEditingController();
  bool _busy = false;

  /// The live conversation about the note just written: the entry being asked
  /// about, and Advary's current question. Both null when nothing is in flight.
  DiaryEntry? _active;
  String? _question;

  @override
  void dispose() {
    _note.dispose();
    _reply.dispose();
    super.dispose();
  }

  void _refresh() {
    ref.invalidate(diaryEntriesProvider);
    ref.invalidate(diaryPatternsProvider);
  }

  Future<void> _write() async {
    final text = _note.text.trim();
    if (text.isEmpty || _busy) return;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      final reply = await ref.read(diaryRepositoryProvider).write(text);
      if (!mounted) return;
      _note.clear();
      setState(() {
        _busy = false;
        _active = reply.entry;
        _question = reply.question; // may be null — then there's simply nothing to ask
      });
      _refresh();
    } catch (e) {
      if (!mounted) return;
      // The note is what matters. Catching everything (not just AppError) so a
      // surprise can never strand the button on a spinner with the text lost.
      setState(() => _busy = false);
      messenger.showSnackBar(SnackBar(
        content: Text(e is AppError ? e.message : "I couldn't save that just now"),
      ));
    }
  }

  Future<void> _answer() async {
    final text = _reply.text.trim();
    final entry = _active;
    final question = _question;
    if (text.isEmpty || entry == null || question == null || _busy) return;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      final reply = await ref.read(diaryRepositoryProvider).answer(entry.id, question: question, answer: text);
      if (!mounted) return;
      _reply.clear();
      setState(() {
        _busy = false;
        _active = reply.entry;
        _question = reply.question;
      });
      _refresh();
    } catch (e) {
      if (!mounted) return;
      // Deliberately NOT clearing _reply on failure: what they typed stays put,
      // ready to send again.
      setState(() => _busy = false);
      messenger.showSnackBar(SnackBar(
        content: Text(e is AppError ? e.message : "I couldn't send that just now"),
      ));
    }
  }

  Future<void> _dismissQuestion() async {
    final entry = _active;
    setState(() {
      _question = null;
      _active = null;
    });
    if (entry != null) {
      try {
        await ref.read(diaryRepositoryProvider).close(entry.id);
      } catch (_) {
        // Waving off a question must never fail loudly — it's already gone from
        // the screen, which is the whole point of waving it off.
      }
    }
    _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final p = AppColors.active;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
      children: [
        if (_question == null) ...[
          Text('What happened today?',
              style: TextStyle(color: p.on, fontSize: 17, fontWeight: FontWeight.w600)),
          const SizedBox(height: 10),
          TextField(
            controller: _note,
            minLines: 2,
            maxLines: 5,
            decoration: const InputDecoration(
              hintText: 'e.g. went to the market and bought fruits',
              border: OutlineInputBorder(),
            ),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: (_busy || _note.text.trim().isEmpty) ? null : _write,
            child: _busy
                ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Save'),
          ),
        ] else
          _QuestionCard(
            question: _question!,
            controller: _reply,
            busy: _busy,
            onSend: _answer,
            onDismiss: _dismissQuestion,
          ),
        const SizedBox(height: 24),
        const _PatternsSection(),
        const SizedBox(height: 8),
        const _RecentEntries(),
      ],
    );
  }
}

class _QuestionCard extends StatelessWidget {
  const _QuestionCard({
    required this.question,
    required this.controller,
    required this.busy,
    required this.onSend,
    required this.onDismiss,
  });
  final String question;
  final TextEditingController controller;
  final bool busy;
  final VoidCallback onSend;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final p = AppColors.active;
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(Icons.help_outline, size: 18, color: p.primary),
            const SizedBox(width: 8),
            Text('Advary asks', style: TextStyle(color: p.muted, fontSize: 12, fontWeight: FontWeight.w700)),
          ]),
          const SizedBox(height: 8),
          Text(question, style: TextStyle(color: p.on, fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          TextField(
            controller: controller,
            autofocus: true,
            textInputAction: TextInputAction.send,
            onSubmitted: (_) => onSend(),
            decoration: const InputDecoration(hintText: 'Your answer', border: OutlineInputBorder(), isDense: true),
          ),
          const SizedBox(height: 12),
          // Both Expanded: the theme makes buttons full-width, so a bare one in
          // a Row gets an infinite tight width and silently fails to lay out.
          Row(children: [
            Expanded(
              child: OutlinedButton(
                // Always available. A diary that won't stop asking is a diary
                // nobody writes in twice.
                onPressed: busy ? null : onDismiss,
                child: const Text('Skip'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton(
                onPressed: busy ? null : onSend,
                child: busy
                    ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Answer'),
              ),
            ),
          ]),
        ],
      ),
    );
  }
}

class _PatternsSection extends ConsumerWidget {
  const _PatternsSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = AppColors.active;
    final patterns = ref.watch(diaryPatternsProvider).valueOrNull;
    if (patterns == null) return const SizedBox.shrink();

    if (!patterns.ready) {
      // Say what's missing rather than pretending to know something. The count
      // is honest and gives the user a reason to keep going.
      final left = (patterns.needed - patterns.entries).clamp(0, patterns.needed);
      return GlassCard(
        child: Row(children: [
          Icon(Icons.insights_outlined, size: 18, color: p.muted),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              left == 0
                  ? "I'm still building a picture of your days."
                  : "Write $left more ${left == 1 ? 'note' : 'notes'} and I'll start telling you what I notice.",
              style: TextStyle(color: p.muted, fontSize: 13, height: 1.4),
            ),
          ),
        ]),
      );
    }

    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(Icons.insights_outlined, size: 18, color: p.primary),
            const SizedBox(width: 8),
            Text('What I notice', style: TextStyle(color: p.on, fontWeight: FontWeight.w700, fontSize: 15)),
          ]),
          const SizedBox(height: 10),
          for (final o in patterns.observations)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Container(width: 4, height: 4,
                      decoration: BoxDecoration(color: p.muted, shape: BoxShape.circle)),
                ),
                const SizedBox(width: 8),
                Expanded(child: Text(o.text, style: TextStyle(color: p.on, fontSize: 13.5, height: 1.4))),
              ]),
            ),
          if (patterns.askQuestion != null) ...[
            const SizedBox(height: 6),
            Text(
              patterns.askQuestion!,
              style: TextStyle(color: p.primary, fontSize: 13.5, fontStyle: FontStyle.italic, height: 1.4),
            ),
          ],
        ],
      ),
    );
  }
}

class _RecentEntries extends ConsumerWidget {
  const _RecentEntries();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = AppColors.active;
    final entries = ref.watch(diaryEntriesProvider).valueOrNull ?? const <DiaryEntry>[];
    if (entries.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 12),
        Text('Your notes', style: TextStyle(color: p.muted, fontSize: 12, fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        for (final e in entries)
          GlassCard(
            margin: const EdgeInsets.symmetric(vertical: 5),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(formatDate(e.entryDate),
                    style: TextStyle(color: p.muted, fontSize: 11, fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text(e.text, style: TextStyle(color: p.on, height: 1.35)),
                for (final d in e.details) ...[
                  const SizedBox(height: 8),
                  Text(d.question, style: TextStyle(color: p.muted, fontSize: 12)),
                  Text(d.answer, style: TextStyle(color: p.on, fontSize: 13)),
                ],
              ],
            ),
          ),
      ],
    );
  }
}
