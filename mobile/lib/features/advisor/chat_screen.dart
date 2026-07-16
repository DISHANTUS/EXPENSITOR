import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/companion/companion_scaffold.dart';
import '../../core/format/money.dart';
import '../../core/onboarding/tour_controller.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/glass.dart';
import '../../core/theme/theme_voice.dart';
import '../../core/theme/vitality.dart';
import 'advisor_chat_repository.dart';
import 'chat_models.dart';
import 'widgets/follow_up_card.dart';
import 'widgets/forecast_card.dart';
import 'widgets/recap_card.dart';
import 'widgets/report_graph.dart';

class _Msg {
  _Msg.user(this.text)
      : turn = null,
        explanation = null;
  _Msg.ai(this.turn)
      : text = null,
        explanation = null;
  _Msg.explain(this.explanation)
      : text = null,
        turn = null;
  final String? text;
  final ChatTurn? turn;
  final Explanation? explanation;
}

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<_Msg> _messages = [];
  final Map<String, String> _followUpAcks = {};   // advice_id -> acknowledgement text
  ChatContext? _session;
  bool _sending = false;
  Timer? _replyPulseTimer;

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    _replyPulseTimer?.cancel();
    super.dispose();
  }

  /// Briefly drives the companion orb's speaking visual on a new AI reply —
  /// separate from real TTS voice (untouched), just a short-lived cue so a
  /// text reply reads as "Advary is speaking", not "text appeared".
  void _pulseOrb() {
    ref.read(chatReplyPulseProvider.notifier).state = true;
    _replyPulseTimer?.cancel();
    _replyPulseTimer = Timer(const Duration(milliseconds: 1200), () {
      if (mounted) ref.read(chatReplyPulseProvider.notifier).state = false;
    });
  }

  Future<void> _send(String text) async {
    final msg = text.trim();
    if (msg.isEmpty || _sending) return;
    _input.clear();
    setState(() {
      _messages.add(_Msg.user(msg));
      _sending = true;
    });
    _scrollDown();
    try {
      final turn = await ref.read(advisorChatRepositoryProvider).send(msg, _session);
      // "show me around" → launch the guided tour (the overlay covers this screen).
      if (turn.type == 'tour') {
        ref.read(tourControllerProvider.notifier).start();
      }
      setState(() {
        _messages.add(_Msg.ai(turn));
        _session = turn.session ?? _session;
        _sending = false;
      });
      _pulseOrb();
    } on AppError catch (e) {
      setState(() {
        _messages.add(_Msg.ai(ChatTurn(type: 'answer', message: e.message)));
        _sending = false;
      });
      _pulseOrb();
    }
    _scrollDown();
  }

  Future<void> _explain(String explainRef) async {
    if (_sending) return;
    setState(() => _sending = true);
    _scrollDown();
    try {
      final explanation = await ref.read(advisorChatRepositoryProvider).explain(explainRef, _session);
      setState(() {
        _messages.add(_Msg.explain(explanation));
        _sending = false;
      });
      _pulseOrb();
    } on AppError catch (e) {
      setState(() {
        _messages.add(_Msg.ai(ChatTurn(type: 'answer', message: e.message)));
        _sending = false;
      });
      _pulseOrb();
    }
    _scrollDown();
  }

  Future<void> _runForecast(List<String> levers) async {
    if (_sending) return;
    setState(() => _sending = true);
    _scrollDown();
    try {
      final fc = await ref.read(advisorChatRepositoryProvider).forecast(levers, _session);
      setState(() {
        _messages.add(_Msg.ai(ChatTurn(
          type: 'forecast', forecast: fc, followUps: fc.followUps,
          explainRef: fc.explainRef, confidence: fc.confidence,
        )));
        _sending = false;
      });
      _pulseOrb();
    } on AppError catch (e) {
      setState(() {
        _messages.add(_Msg.ai(ChatTurn(type: 'answer', message: e.message)));
        _sending = false;
      });
      _pulseOrb();
    }
    _scrollDown();
  }

  /// Returns null once answered, or an inline notice for the card to show
  /// (a "say more" nudge, or an error) — see [FollowUpCard.onAnswer].
  Future<String?> _answerFollowUp(String adviceId, String value, {String? detail}) async {
    if (_followUpAcks.containsKey(adviceId)) return null;
    try {
      final ack = await ref.read(advisorChatRepositoryProvider).answerFollowUp(adviceId, value, detail: detail);
      // Too thin a reason: stays pending for one more try — keep the card
      // open with the nudge inline instead of locking it as answered.
      if (ack.needsMoreDetail) return ack.acknowledged;
      final text = ack.lessonSuggestion != null && ack.lessonSuggestion!.isNotEmpty
          ? '${ack.acknowledged}\n💡 ${ack.lessonSuggestion}'
          : ack.acknowledged;
      setState(() => _followUpAcks[adviceId] = text);
      _scrollDown();
      return null;
    } on AppError catch (e) {
      return e.message;   // the typed reason stays put, ready to retry
    }
  }

  Future<String?> _answerReflection(String trigger, String value) async {
    if (_followUpAcks.containsKey('refl:$trigger')) return null;
    try {
      final ack = await ref.read(advisorChatRepositoryProvider).answerReflection(trigger, value);
      setState(() => _followUpAcks['refl:$trigger'] = ack);
      _scrollDown();
      return null;
    } on AppError catch (e) {
      return e.message;
    }
  }

  Future<void> _forgetLesson(String lessonId) async {
    try {
      await ref.read(advisorChatRepositoryProvider).forgetLesson(lessonId);
      setState(() => _messages.add(_Msg.ai(const ChatTurn(type: 'answer', message: 'Done — I’ve forgotten that lesson. Ask me to restore it anytime.'))));
    } on AppError catch (e) {
      setState(() => _messages.add(_Msg.ai(ChatTurn(type: 'answer', message: e.message))));
    }
    _scrollDown();
  }

  void _scrollDown() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) _scroll.animateTo(_scroll.position.maxScrollExtent, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
    });
  }

  @override
  Widget build(BuildContext context) {
    return CompanionScaffold(
      title: 'Chat With Advisor',
      commentary: 'Ask me about your money — try “show my weekly report”.',
      child: Column(
        children: [
          Expanded(
            child: _messages.isEmpty
                ? _starters()
                : ListView.builder(
                    controller: _scroll,
                    padding: const EdgeInsets.all(12),
                    itemCount: _messages.length + (_sending ? 1 : 0),
                    itemBuilder: (context, i) {
                      if (i >= _messages.length) return const _ThemedTyping();
                      final m = _messages[i];
                      Widget bubble;
                      if (m.text != null) {
                        bubble = _UserBubble(m.text!);
                      } else if (m.explanation != null) {
                        bubble = _ExplanationCard(m.explanation!);
                      } else {
                        bubble = _AiTurn(m.turn!, onTap: _send, onExplain: _explain, onLever: _runForecast,
                            onAnswerFollowUp: _answerFollowUp, onAnswerReflection: _answerReflection,
                            onForgetLesson: _forgetLesson, followUpAcks: _followUpAcks,
                            onOpen: (r) => context.go(r));
                      }
                      // Every new bubble fades, slides up slightly, and grows in from
                      // ~95% — a real entrance, not just an appended list row.
                      return bubble.animate().fadeIn(duration: 260.ms).slideY(begin: 0.08, end: 0).scale(
                          begin: const Offset(0.95, 0.95), end: const Offset(1, 1), duration: 260.ms);
                    },
                  ),
          ),
          _inputBar(),
        ],
      ),
    );
  }

  Widget _starters() => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('What would you like to know?'),
            const SizedBox(height: 12),
            Wrap(spacing: 8, runSpacing: 8, alignment: WrapAlignment.center, children: [
              for (final s in const ['Weekly report', 'Monthly report', 'When will I reach my goal?'])
                ActionChip(label: Text(s), onPressed: () => _send(s.toLowerCase())),
            ]),
          ],
        ),
      );

  Widget _inputBar() => SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _input,
                  textInputAction: TextInputAction.send,
                  onSubmitted: _send,
                  decoration: const InputDecoration(hintText: 'Ask anything…', isDense: true),
                ),
              ),
              const SizedBox(width: 8),
              _SendButton(sending: _sending, onSend: () => _send(_input.text)),
            ],
          ),
        ),
      );
}

/// Wraps the send button in a scrolling diagonal-stripe background when the
/// active theme's `motion.movingStripes` is set (Comic, Velocity, Riot) — the
/// Flutter equivalent of the "Ask Advary" button motion validated on the
/// Comic HTML prototype. Every other theme gets a plain filled icon button.
class _SendButton extends StatelessWidget {
  const _SendButton({required this.sending, required this.onSend});
  final bool sending;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final p = AppColors.active;
    final button = IconButton.filled(onPressed: sending ? null : onSend, icon: const Icon(Icons.send));
    if (!p.motion.movingStripes || sending) return button;
    return ClipOval(
      child: MovingStripeBackground(
        stripeColor: (p.onPrimaryOverride ?? Colors.white).withValues(alpha: 0.25),
        pitch: 10,
        child: button,
      ),
    );
  }
}

class _UserBubble extends StatelessWidget {
  const _UserBubble(this.text);
  final String text;
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Align(
      alignment: Alignment.centerRight,
      child: GlassCard(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        radius: 14,
        gradient: LinearGradient(colors: [cs.primaryContainer, cs.primaryContainer]),
        child: Text(text),
      ),
    );
  }
}

/// The "Advary is thinking" indicator — a personality-driven variant for a
/// few themes deep (Terminal, Cyberpunk, Comic); every other theme keeps the
/// plain spinner. One themed-variant branch, not a new loading-state system.
class _ThemedTyping extends StatelessWidget {
  const _ThemedTyping();

  @override
  Widget build(BuildContext context) {
    final p = AppColors.active;
    Widget child = switch (p.id) {
      'terminal' => Row(mainAxisSize: MainAxisSize.min, children: [
          Text('Thinking', style: TextStyle(color: p.primary, fontFamily: 'monospace', fontWeight: FontWeight.w600)),
          const SizedBox(width: 4),
          const BlinkingCursor(width: 6, height: 13),
        ]),
      'cyberpunk' => Row(mainAxisSize: MainAxisSize.min, children: [
          Text('Scanning…', style: TextStyle(color: p.primary, fontFamily: 'monospace', fontWeight: FontWeight.w600)),
        ]),
      'comic' => Row(mainAxisSize: MainAxisSize.min, children: [
          HalftoneDots(color: p.primary, child: const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))),
        ]),
      _ => const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2)),
    };
    return Padding(padding: const EdgeInsets.all(8), child: Align(alignment: Alignment.centerLeft, child: child));
  }
}

class _AiTurn extends StatelessWidget {
  const _AiTurn(this.turn, {required this.onTap, required this.onExplain, required this.onLever,
      required this.onAnswerFollowUp, required this.onAnswerReflection, required this.onForgetLesson,
      required this.followUpAcks, required this.onOpen});
  final ChatTurn turn;
  final void Function(String) onTap;
  final void Function(String) onExplain;
  final void Function(List<String>) onLever;
  final Future<String?> Function(String adviceId, String value, {String? detail}) onAnswerFollowUp;
  final Future<String?> Function(String trigger, String value) onAnswerReflection;
  final void Function(String lessonId) onForgetLesson;
  final Map<String, String> followUpAcks;
  final void Function(String route) onOpen;

  @override
  Widget build(BuildContext context) {
    // Forecast turns own their chips (levers + follow-ups + evidence).
    if (turn.forecast != null) {
      final f = turn.forecast!;
      return Align(
        alignment: Alignment.centerLeft,
        child: ForecastCard(
          f,
          onTap: onTap,
          onExplain: onExplain,
          onLever: (refStr) => onLever([...f.appliedLevers.map((l) => l.ref), refStr]),
        ),
      );
    }
    // Learning-loop check-in.
    if (turn.followUp != null) {
      final q = turn.followUp!;
      return Align(
        alignment: Alignment.centerLeft,
        child: FollowUpCard(q, answered: followUpAcks[q.id],
            onAnswer: (v, {detail}) => onAnswerFollowUp(q.id, v, detail: detail)),
      );
    }
    // Month-end / win reflection (reuses the check-in card).
    if (turn.reflection != null) {
      final r = turn.reflection!;
      final q = FollowUpQuestion(id: 'refl:${r.trigger}', kind: 'reflection', importance: r.importance,
          claim: '', question: r.question, options: r.options);
      return Align(
        alignment: Alignment.centerLeft,
        child: FollowUpCard(q, answered: followUpAcks['refl:${r.trigger}'],
            onAnswer: (v, {detail}) => onAnswerReflection(r.trigger, v)),
      );
    }
    // Structured "what do you know about me?".
    if (turn.recap != null) {
      return Align(alignment: Alignment.centerLeft, child: RecapCard(turn.recap!, onForgetLesson: onForgetLesson));
    }
    final ref = turn.explainRef;
    return Align(
      alignment: Alignment.centerLeft,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (turn.report != null)
            _ReportCard(turn.report!)
          else if (turn.drilldown != null)
            _DrilldownCard(turn.drilldown!)
          else if (turn.message != null)
            _bubble(context, turn.message!),
          // How-to / tour: offer to open the screen the companion is describing.
          if (turn.route != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: FilledButton.tonalIcon(
                icon: const Icon(Icons.open_in_new, size: 18),
                label: const Text('Open it'),
                onPressed: () => onOpen(turn.route!),
              ),
            ),
          if (ref != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Wrap(spacing: 8, children: [
                ActionChip(label: const Text('Why does this matter?'), onPressed: () => onExplain(ref)),
                ActionChip(label: const Text('Show evidence'), onPressed: () => onExplain(ref)),
              ]),
            ),
          if (turn.options.isNotEmpty) _chips(turn.options),
          if (turn.followUps.isNotEmpty) _chips(turn.followUps),
        ],
      ),
    );
  }

  Widget _bubble(BuildContext context, String text) {
    final p = AppColors.active;
    final voiced = themeVoice(text, p.personality);
    return GlassCard(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      radius: 14,
      child: p.id == 'terminal'
          // Terminal's signature: the reply types itself out, cursor and all.
          ? Row(mainAxisSize: MainAxisSize.min, children: [
              Flexible(child: TypewriterText(voiced, style: TextStyle(color: p.primary, fontFamily: 'monospace'))),
              const SizedBox(width: 4),
              const BlinkingCursor(width: 6, height: 14),
            ])
          : Text(voiced),
    );
  }

  Widget _chips(List<ChatOption> opts) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [for (final o in opts) ActionChip(label: Text(o.label), onPressed: () => onTap(o.message))],
        ),
      );
}

class _ReportCard extends StatelessWidget {
  const _ReportCard(this.r);
  final ReportSession r;

  @override
  Widget build(BuildContext context) {
    final cur = r.summary.currency;
    final chips = <Widget>[
      _chip('Spent', formatMoney(r.summary.totalSpent, cur)),
      _chip('Income', formatMoney(r.summary.totalIncome, cur)),
      _chip('Saved', formatMoney(r.summary.saved, cur)),
      if (r.summary.redDays > 0) _chip('🔴 Red days', '${r.summary.redDays}'),
      if (r.summary.crownDays > 0) _chip('👑 Saved days', '${r.summary.crownDays}'),
    ];
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(r.periodLabel, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 10),
            ReportGraph(r.series),
            const SizedBox(height: 12),
            Wrap(spacing: 8, runSpacing: 8, children: chips),
            const SizedBox(height: 12),
            if (r.delta != null) _DeltaSection(r.delta!),
            Text(r.story.beginning),
            const SizedBox(height: 4),
            Text(r.story.middle),
            const SizedBox(height: 4),
            Text(r.story.end),
            if (r.confidence == 'low') ...[
              const SizedBox(height: 8),
              Text('Based on limited data so far.',
                  style: TextStyle(fontStyle: FontStyle.italic, color: Theme.of(context).colorScheme.outline)),
            ],
            if (r.timelineEvents.isNotEmpty) ...[
              const SizedBox(height: 10),
              for (final e in r.timelineEvents) Text('• ${e.label}', style: Theme.of(context).textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }

  Widget _chip(String label, String value) =>
      Chip(label: Text('$label  $value'), visualDensity: VisualDensity.compact);
}

class _DeltaSection extends StatelessWidget {
  const _DeltaSection(this.delta);
  final PeriodDelta delta;

  String _pct(double? p) => p == null ? '—' : '${p >= 0 ? '↑' : '↓'}${p.abs().toStringAsFixed(0)}%';
  Color _col(BuildContext c, double? p) =>
      p == null ? Theme.of(c).colorScheme.outline : (p >= 0 ? Colors.green.shade700 : Theme.of(c).colorScheme.error);

  @override
  Widget build(BuildContext context) {
    Widget line(String label, double? p) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 1),
          child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Text(label),
            Text(_pct(p), style: TextStyle(color: _col(context, p), fontWeight: FontWeight.w600)),
          ]),
        );
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(children: [
        line('Spending', delta.spentPct),
        line('Income', delta.incomePct),
        line('Savings', delta.savedPct),
      ]),
    );
  }
}

class _ExplanationCard extends StatelessWidget {
  const _ExplanationCard(this.e);
  final Explanation e;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      color: cs.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.fact_check_outlined, size: 18, color: cs.primary),
              const SizedBox(width: 6),
              const Text('Here’s my reasoning', style: TextStyle(fontWeight: FontWeight.w600)),
            ]),
            const SizedBox(height: 8),
            Text(e.claim),
            if (e.whyItMatters != null && e.whyItMatters!.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(e.whyItMatters!, style: TextStyle(color: cs.error)),
            ],
            const SizedBox(height: 10),
            const Text('Evidence', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 12)),
            const SizedBox(height: 4),
            for (final it in e.evidence)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                  Expanded(child: Text(it.label + (it.when != null ? '  (${it.when})' : ''))),
                  if (it.value != null) Text(it.value!, style: const TextStyle(fontWeight: FontWeight.w600)),
                ]),
              ),
            const SizedBox(height: 8),
            Text('Confidence: ${e.confidence}',
                style: TextStyle(fontStyle: FontStyle.italic, color: cs.outline, fontSize: 12)),
          ],
        ),
      ),
    );
  }
}

class _DrilldownCard extends StatelessWidget {
  const _DrilldownCard(this.d);
  final DrilldownResult d;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(d.title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(d.explanation, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 8),
            if (d.items.isEmpty)
              const Text('Nothing here for this period.')
            else
              for (final it in d.items.take(15))
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(it.label, maxLines: 1, overflow: TextOverflow.ellipsis),
                            if (it.subtitle != null && it.subtitle!.isNotEmpty)
                              Text(it.subtitle!, style: Theme.of(context).textTheme.bodySmall),
                          ],
                        ),
                      ),
                      if (it.amount != null)
                        Text(formatMoney(it.amount, it.currency ?? d.currency),
                            style: const TextStyle(fontWeight: FontWeight.w600)),
                    ],
                  ),
                ),
            if (d.total != null) ...[
              const Divider(),
              Align(
                alignment: Alignment.centerRight,
                child: Text('Total ${formatMoney(d.total, d.currency)}', style: const TextStyle(fontWeight: FontWeight.w700)),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
