import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/budget/budget_plan_repository.dart';
import '../../core/intervention/intervention_controller.dart';
import '../../core/notifications/local_notification_service.dart';
import '../../core/settings/settings_repository.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/glass.dart';
import '../advisor/advisor_chat_repository.dart';
import '../advisor/widgets/follow_up_card.dart';
import 'budget_repository.dart';
import 'planning_intelligence.dart';
import 'planning_repository.dart';

/// The return-visit face of the Planning screen. The basics are already known,
/// so instead of re-asking them this asks "what are you planning?" and runs a
/// short, adaptive follow-up per intent — a purchase, a subscription, or a
/// savings goal — writing a real goal/recurring rule so it flows into the plan
/// and the daily allowance.
///
/// The front door is free text, not a menu: whatever you type is read by the
/// planning-intent layer (rules first, the local model for anything the rules
/// can't place), which picks the flow AND pre-fills what you already said, so
/// the flow only ever asks for what's still missing. Say everything in one line
/// and you get one confirm step; say "my headphone broke" and it asks the rest.
/// The tiles below stay as a plain way in, and nothing depends on the model
/// being reachable — with no model, the rules still route the common phrasings
/// and the tiles always work.
class PlanningHub extends ConsumerStatefulWidget {
  const PlanningHub({super.key});

  @override
  ConsumerState<PlanningHub> createState() => _PlanningHubState();
}

enum _Intent { none, buy, subscription, save, other }

class _PlanningHubState extends ConsumerState<PlanningHub> {
  _Intent _intent = _Intent.none;
  PlanningIntent? _seed;
  final _free = TextEditingController();
  bool _reading = false;

  String get _currency => ref.read(userSettingsProvider).valueOrNull?.baseCurrency ?? 'INR';

  @override
  void dispose() {
    _free.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return switch (_intent) {
      _Intent.none => _chooser(),
      _Intent.buy => _BuyFlow(currency: _currency, seed: _seed, onDone: _reset, onBack: _reset),
      _Intent.save => _SaveFlow(currency: _currency, seed: _seed, onDone: _reset, onBack: _reset),
      _Intent.subscription =>
        _SubscriptionFlow(currency: _currency, seed: _seed, onDone: _reset, onBack: _reset),
      _Intent.other => _OtherFlow(onBack: _reset, text: _free.text.trim()),
    };
  }

  void _reset() => setState(() {
        _intent = _Intent.none;
        _seed = null;
        _free.clear();
      });

  void _pick(_Intent i) => setState(() {
        _intent = i;
        _seed = null;
      });

  Future<void> _readFreeText() async {
    final text = _free.text.trim();
    if (text.isEmpty || _reading) return;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _reading = true);
    PlanningIntent intent;
    try {
      intent = await ref.read(planningRepositoryProvider).interpret(text);
    } catch (e) {
      // Deliberately catching everything, not just AppError: anything that
      // escapes here strands _reading at true, which leaves a spinner turning
      // over a dead button forever. Understanding is a convenience, never a
      // gate — if it fails, say so plainly and leave the tiles there to tap.
      if (!mounted) return;
      setState(() => _reading = false);
      final message = e is AppError ? e.message : "I couldn't read that just now";
      return _toast(messenger, '$message — you can still pick below.');
    }
    if (!mounted) return;
    setState(() {
      _reading = false;
      _seed = intent;
      _intent = switch (intent.kind) {
        'buy' => _Intent.buy,
        'save' => _Intent.save,
        'subscription' => _Intent.subscription,
        _ => _Intent.other,
      };
    });
  }

  Widget _chooser() {
    final p = AppColors.active;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
      children: [
        // Advary's own questions come first — the orb's "!" promises they're
        // here, so they must actually be here.
        const _PendingQuestions(),
        Text('What are you planning?', style: TextStyle(color: p.on, fontSize: 17, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        Text(
          'Say it however you like — "buy headphones for 3000 by december", or just "my headphone broke".',
          style: TextStyle(color: p.muted, height: 1.4, fontSize: 13),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _free,
          textInputAction: TextInputAction.send,
          onSubmitted: (_) => _readFreeText(),
          onChanged: (_) => setState(() {}),
          decoration: InputDecoration(
            hintText: 'Tell me in your words',
            border: const OutlineInputBorder(),
            isDense: true,
            suffixIcon: _reading
                ? const Padding(
                    padding: EdgeInsets.all(12),
                    child: SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                  )
                : IconButton(
                    icon: const Icon(Icons.arrow_forward),
                    tooltip: 'Read this',
                    onPressed: _free.text.trim().isEmpty ? null : _readFreeText,
                  ),
          ),
        ),
        const SizedBox(height: 20),
        Text('Or pick one', style: TextStyle(color: p.muted, fontSize: 13)),
        const SizedBox(height: 8),
        _ChooserTile(
          icon: Icons.shopping_bag_outlined,
          title: 'Buy something',
          subtitle: 'A phone, headphones, a trip — I\'ll plan the saving for it',
          onTap: () => _pick(_Intent.buy),
        ),
        _ChooserTile(
          icon: Icons.subscriptions_outlined,
          title: 'Start a subscription',
          subtitle: 'Netflix, Spotify, a gym — I\'ll fit the monthly cost in',
          onTap: () => _pick(_Intent.subscription),
        ),
        _ChooserTile(
          icon: Icons.savings_outlined,
          title: 'Save for a goal',
          subtitle: 'An emergency fund, a big purchase, anything',
          onTap: () => _pick(_Intent.save),
        ),
        _ChooserTile(
          icon: Icons.chat_bubble_outline,
          title: 'Something else',
          subtitle: 'Just tell me in your words',
          onTap: () => _pick(_Intent.other),
        ),
      ],
    );
  }
}

/// Advary's due check-in questions, answered right here. This is the page the
/// orb's "!" points at, so it renders nothing at all when there's nothing to
/// ask — an empty "Questions" heading would make the orb look like a liar.
class _PendingQuestions extends ConsumerWidget {
  const _PendingQuestions();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final p = AppColors.active;
    final questions = ref.watch(dueFollowUpsProvider).valueOrNull ?? const [];
    if (questions.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          Icon(Icons.help_outline, size: 18, color: p.primary),
          const SizedBox(width: 6),
          Text(
            questions.length == 1 ? 'A question for you' : '${questions.length} questions for you',
            style: TextStyle(color: p.on, fontWeight: FontWeight.w700, fontSize: 15),
          ),
        ]),
        const SizedBox(height: 8),
        for (final q in questions)
          FollowUpCard(
            q,
            onAnswer: (value, {detail}) async {
              try {
                final ack = await ref.read(advisorChatRepositoryProvider).answerFollowUp(q.id, value, detail: detail);
                // A reason judged too thin: keep the card open and say so,
                // rather than silently dropping what they typed.
                if (ack.needsMoreDetail) return ack.acknowledged;
                await ref.read(localNotificationServiceProvider).cancelForAdvice(q.id);
                ref.invalidate(dueFollowUpsProvider);
                // Also stands the orb down — the "!" must clear the moment the
                // last question is answered.
                ref.invalidate(questionInterventionsProvider);
                return null;
              } on AppError catch (e) {
                return e.message; // the typed reason stays put, ready to retry
              }
            },
          ),
        const SizedBox(height: 20),
      ],
    );
  }
}

class _ChooserTile extends StatelessWidget {
  const _ChooserTile({required this.icon, required this.title, required this.subtitle, required this.onTap});
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final p = AppColors.active;
    return GlassCard(
      margin: const EdgeInsets.symmetric(vertical: 6),
      onTap: onTap,
      child: Row(children: [
        Icon(icon, color: p.primary, size: 26),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: TextStyle(color: p.on, fontWeight: FontWeight.w700, fontSize: 16)),
            const SizedBox(height: 2),
            Text(subtitle, style: TextStyle(color: p.muted, fontSize: 13)),
          ]),
        ),
        Icon(Icons.chevron_right, color: p.muted),
      ]),
    );
  }
}

// --- shared step scaffolding ------------------------------------------------

/// A single question in a flow: a prompt, an input, and Back/Next. Kept generic
/// so a flow is a list of these rather than a fixed switch — new question types
/// slot in without reshaping the flow.
class _QuestionStep extends StatelessWidget {
  const _QuestionStep({
    required this.prompt,
    required this.child,
    required this.onBack,
    this.onNext,
    this.nextLabel = 'Next',
    this.busy = false,
    this.note,
  });
  final String prompt;
  final Widget child;
  final VoidCallback onBack;
  final VoidCallback? onNext;
  final String nextLabel;
  final bool busy;

  /// What Advary took from the user's own sentence, shown back so a misread is
  /// visible and correctable (Back walks into the pre-filled earlier steps)
  /// rather than silently baked into a real goal.
  final String? note;

  @override
  Widget build(BuildContext context) {
    final p = AppColors.active;
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 32),
      children: [
        if (note != null) ...[
          Row(children: [
            Icon(Icons.auto_awesome, size: 14, color: p.primary),
            const SizedBox(width: 6),
            Expanded(child: Text(note!, style: TextStyle(color: p.muted, fontSize: 12.5))),
          ]),
          const SizedBox(height: 12),
        ],
        Text(prompt, style: TextStyle(color: p.on, fontSize: 17, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        child,
        const SizedBox(height: 24),
        // Every button MUST be Expanded here. The theme gives buttons
        // minimumSize: Size.fromHeight(50) — i.e. width: double.infinity — so a
        // bare button inside a Row gets an infinite tight width and fails
        // layout: invisible and untappable in release, where the assert is
        // compiled out. Expanded bounds it. Same pattern as the interview's
        // _nav().
        Row(
          children: [
            Expanded(child: OutlinedButton(onPressed: busy ? null : onBack, child: const Text('Back'))),
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton(
                onPressed: (busy || onNext == null) ? null : onNext,
                child: busy
                    ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : Text(nextLabel),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

Widget _field(TextEditingController c, String label, {bool number = false, ValueChanged<String>? onChanged}) {
  return TextField(
    controller: c,
    autofocus: true,
    keyboardType: number ? const TextInputType.numberWithOptions(decimal: true) : TextInputType.text,
    onChanged: onChanged,
    decoration: InputDecoration(labelText: label, border: const OutlineInputBorder(), isDense: true),
  );
}

void _toast(ScaffoldMessengerState m, String msg) => m.showSnackBar(SnackBar(content: Text(msg)));

/// 3000.0 -> "3000" (a text field showing "3000.0" looks like a bug).
String _plain(double v) => v == v.roundToDouble() ? v.toInt().toString() : v.toString();

/// A one-line "here's what I took from your sentence" for a seeded flow. Only
/// ever lists what the user actually said — it must never imply we know
/// something they didn't tell us.
String? _seedNote(PlanningIntent? seed, String currency) {
  if (seed == null) return null;
  final parts = [
    if (seed.item != null) seed.item!,
    if (seed.amount != null) '$currency ${_plain(seed.amount!)}',
    if (seed.targetDate != null) 'by ${seed.targetDate!.day}/${seed.targetDate!.month}/${seed.targetDate!.year}',
  ];
  if (parts.isEmpty) return null;
  return 'From what you said: ${parts.join(' · ')}. Change anything with Back.';
}

// --- Buy flow ---------------------------------------------------------------

class _BuyFlow extends ConsumerStatefulWidget {
  const _BuyFlow({required this.currency, required this.onDone, required this.onBack, this.seed});
  final String currency;
  final VoidCallback onDone;
  final VoidCallback onBack;
  final PlanningIntent? seed;
  @override
  ConsumerState<_BuyFlow> createState() => _BuyFlowState();
}

class _BuyFlowState extends ConsumerState<_BuyFlow> {
  int _step = 0;
  bool _busy = false;
  final _name = TextEditingController();
  final _cost = TextEditingController();
  DateTime? _by;

  @override
  void initState() {
    super.initState();
    final seed = widget.seed;
    if (seed == null) return;
    _name.text = seed.item ?? '';
    if (seed.amount != null) _cost.text = _plain(seed.amount!);
    _by = seed.targetDate;
    // Skip straight to the first thing we DON'T know. Everything before it is
    // pre-filled and still reachable via Back, so a misread is correctable.
    _step = _name.text.isEmpty
        ? 0
        : _cost.text.isEmpty
            ? 1
            : 2;
  }

  @override
  void dispose() {
    _name.dispose();
    _cost.dispose();
    super.dispose();
  }

  void _next() => setState(() => _step++);
  void _prev() => _step == 0 ? widget.onBack() : setState(() => _step--);

  Future<void> _submit() async {
    final messenger = ScaffoldMessenger.of(context);
    final cost = double.tryParse(_cost.text.trim());
    if (cost == null || cost <= 0) return _toast(messenger, 'Enter a cost above zero.');
    setState(() => _busy = true);
    try {
      await ref.read(budgetRepositoryProvider).createSavingsGoal(
            name: _name.text.trim().isEmpty ? 'A purchase' : _name.text.trim(),
            amount: cost.toString(),
            currency: widget.currency,
            kind: 'custom_goal',
            targetDate: _by,
            reason: 'Planning to buy ${_name.text.trim()}',
          );
      _invalidatePlan(ref);
      widget.onDone();
      _toast(messenger, 'Added — I\'ll work "${_name.text.trim()}" into your plan.');
    } on AppError catch (e) {
      if (mounted) setState(() => _busy = false);
      _toast(messenger, e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final note = _seedNote(widget.seed, widget.currency);
    switch (_step) {
      case 0:
        return _QuestionStep(
          prompt: 'What are you planning to buy?',
          note: note,
          onBack: _prev,
          onNext: _name.text.trim().isEmpty ? null : _next,
          child: _field(_name, 'e.g. Headphones', onChanged: (_) => setState(() {})),
        );
      case 1:
        return _QuestionStep(
          prompt: 'Roughly how much does ${_name.text.trim()} cost?',
          note: note,
          onBack: _prev,
          onNext: (double.tryParse(_cost.text.trim()) ?? 0) > 0 ? _next : null,
          child: _field(_cost, 'Cost (${widget.currency})', number: true, onChanged: (_) => setState(() {})),
        );
      default:
        // The date is REQUIRED, not optional: the amount we collected is the
        // total cost, so this must be a one-off custom_goal — which the
        // backend rightly refuses without a target_date. It's also what makes
        // the plan real (cost spread over the time left = what to set aside).
        return _QuestionStep(
          prompt: 'When do you want it by?',
          note: note,
          onBack: _prev,
          onNext: _by == null ? null : _submit,
          nextLabel: 'Add to plan',
          busy: _busy,
          child: _DatePickerRow(
            value: _by,
            hint: 'Pick a target date',
            onPick: (d) => setState(() => _by = d),
          ),
        );
    }
  }
}

// --- Save flow (a goal without a specific item) -----------------------------

class _SaveFlow extends ConsumerStatefulWidget {
  const _SaveFlow({required this.currency, required this.onDone, required this.onBack, this.seed});
  final String currency;
  final VoidCallback onDone;
  final VoidCallback onBack;
  final PlanningIntent? seed;
  @override
  ConsumerState<_SaveFlow> createState() => _SaveFlowState();
}

class _SaveFlowState extends ConsumerState<_SaveFlow> {
  int _step = 0;
  bool _busy = false;
  final _name = TextEditingController();
  final _amount = TextEditingController();
  DateTime? _by;

  @override
  void initState() {
    super.initState();
    final seed = widget.seed;
    if (seed == null) return;
    _name.text = seed.item ?? '';
    if (seed.amount != null) _amount.text = _plain(seed.amount!);
    _by = seed.targetDate;
    _step = _name.text.isEmpty
        ? 0
        : _amount.text.isEmpty
            ? 1
            : 2;
  }

  @override
  void dispose() {
    _name.dispose();
    _amount.dispose();
    super.dispose();
  }

  void _next() => setState(() => _step++);
  void _prev() => _step == 0 ? widget.onBack() : setState(() => _step--);

  Future<void> _submit() async {
    final messenger = ScaffoldMessenger.of(context);
    final amt = double.tryParse(_amount.text.trim());
    if (amt == null || amt <= 0) return _toast(messenger, 'Enter an amount above zero.');
    setState(() => _busy = true);
    try {
      await ref.read(budgetRepositoryProvider).createSavingsGoal(
            name: _name.text.trim().isEmpty ? 'Savings goal' : _name.text.trim(),
            amount: amt.toString(),
            currency: widget.currency,
            // Always custom_goal: the amount collected is a TOTAL target, and
            // monthly_target would misread it as "save this much every month".
            kind: 'custom_goal',
            targetDate: _by,
            reason: 'Saving for ${_name.text.trim()}',
          );
      _invalidatePlan(ref);
      widget.onDone();
      _toast(messenger, 'Goal added — it\'s in your plan now.');
    } on AppError catch (e) {
      if (mounted) setState(() => _busy = false);
      _toast(messenger, e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final note = _seedNote(widget.seed, widget.currency);
    switch (_step) {
      case 0:
        return _QuestionStep(
          prompt: 'What are you saving for?',
          note: note,
          onBack: _prev,
          onNext: _name.text.trim().isEmpty ? null : _next,
          child: _field(_name, 'e.g. Emergency fund', onChanged: (_) => setState(() {})),
        );
      case 1:
        return _QuestionStep(
          prompt: 'How much do you want to save?',
          note: note,
          onBack: _prev,
          onNext: (double.tryParse(_amount.text.trim()) ?? 0) > 0 ? _next : null,
          child: _field(_amount, 'Target (${widget.currency})', number: true, onChanged: (_) => setState(() {})),
        );
      default:
        // Required for the same reason as the buy flow — a total needs a
        // deadline to become a plan, and custom_goal demands one.
        return _QuestionStep(
          prompt: 'By when do you want to have it saved?',
          note: note,
          onBack: _prev,
          onNext: _by == null ? null : _submit,
          nextLabel: 'Add goal',
          busy: _busy,
          child: _DatePickerRow(
            value: _by,
            hint: 'Pick a target date',
            onPick: (d) => setState(() => _by = d),
          ),
        );
    }
  }
}

// --- Subscription flow (with domain-knowledge advice) -----------------------

class _SubscriptionFlow extends ConsumerStatefulWidget {
  const _SubscriptionFlow({required this.currency, required this.onDone, required this.onBack, this.seed});
  final String currency;
  final VoidCallback onDone;
  final VoidCallback onBack;
  final PlanningIntent? seed;
  @override
  ConsumerState<_SubscriptionFlow> createState() => _SubscriptionFlowState();
}

class _SubscriptionFlowState extends ConsumerState<_SubscriptionFlow> {
  int _step = 0;
  bool _busy = false;
  final _name = TextEditingController();
  final _amount = TextEditingController();
  final _purpose = TextEditingController();
  bool _shared = false;
  int _renewDay = DateTime.now().day;
  SubscriptionAdvice? _advice;

  @override
  void initState() {
    super.initState();
    final seed = widget.seed;
    if (seed == null) return;
    _name.text = seed.item ?? '';
    if (seed.amount != null) _amount.text = _plain(seed.amount!);
    // Only the name/amount are skippable. The remaining questions (what it's
    // for, shared or solo) are what the advice is actually built from, so they
    // still get asked — a seed shortens the flow, it doesn't hollow it out.
    _step = _name.text.isEmpty
        ? 0
        : _amount.text.isEmpty
            ? 1
            : 2;
  }

  @override
  void dispose() {
    _name.dispose();
    _amount.dispose();
    _purpose.dispose();
    super.dispose();
  }

  void _prev() => _step == 0 ? widget.onBack() : setState(() => _step--);

  void _computeAdviceThenAdvance() {
    final amt = double.tryParse(_amount.text.trim()) ?? 0;
    _advice = subscriptionAdvice(name: _name.text.trim(), monthly: amt, shared: _shared, currency: widget.currency);
    setState(() => _step++);
  }

  Future<void> _submit() async {
    final messenger = ScaffoldMessenger.of(context);
    final amt = double.tryParse(_amount.text.trim());
    if (amt == null || amt <= 0) return _toast(messenger, 'Enter an amount above zero.');
    setState(() => _busy = true);
    final reason = [
      if (_purpose.text.trim().isNotEmpty) _purpose.text.trim(),
      _shared ? 'shared plan' : 'personal plan',
    ].join(' · ');
    try {
      await ref.read(budgetRepositoryProvider).createRecurringRule(
            ruleType: 'subscription',
            label: _name.text.trim().isEmpty ? 'Subscription' : _name.text.trim(),
            amount: amt.toString(),
            currency: widget.currency,
            recurrenceDay: _renewDay,
            startDate: DateTime.now(),
            reason: reason,
          );
      _invalidatePlan(ref);
      widget.onDone();
      _toast(messenger, '${_name.text.trim()} added — I\'ll budget for it each month.');
    } on AppError catch (e) {
      if (mounted) setState(() => _busy = false);
      _toast(messenger, e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = AppColors.active;
    final note = _seedNote(widget.seed, widget.currency);
    switch (_step) {
      case 0:
        return _QuestionStep(
          prompt: 'Which subscription?',
          note: note,
          onBack: _prev,
          onNext: _name.text.trim().isEmpty ? null : () => setState(() => _step++),
          child: _field(_name, 'e.g. Netflix', onChanged: (_) => setState(() {})),
        );
      case 1:
        return _QuestionStep(
          prompt: 'How much is it per month?',
          note: note,
          onBack: _prev,
          onNext: (double.tryParse(_amount.text.trim()) ?? 0) > 0 ? () => setState(() => _step++) : null,
          child: _field(_amount, 'Monthly (${widget.currency})', number: true, onChanged: (_) => setState(() {})),
        );
      case 2:
        return _QuestionStep(
          prompt: 'What\'s it for? (optional — be as specific as you like)',
          note: note,
          onBack: _prev,
          onNext: () => setState(() => _step++),
          child: _field(_purpose, 'e.g. to watch a specific series'),
        );
      case 3:
        return _QuestionStep(
          prompt: 'Will anyone else use it, or just you?',
          note: note,
          onBack: _prev,
          onNext: _computeAdviceThenAdvance,
          child: Wrap(spacing: 10, children: [
            ChoiceChip(
              label: const Text('Just me'),
              selected: !_shared,
              onSelected: (_) => setState(() => _shared = false),
            ),
            ChoiceChip(
              label: const Text('Shared with others'),
              selected: _shared,
              onSelected: (_) => setState(() => _shared = true),
            ),
          ]),
        );
      case 4:
        // Advice step — only meaningful when there's something to suggest;
        // otherwise skip straight to the renewal day.
        if (_advice == null) {
          _step = 5;
          return const SizedBox.shrink();
        }
        return _QuestionStep(
          prompt: _advice!.headline,
          onBack: _prev,
          onNext: () => setState(() => _step = 5),
          nextLabel: 'Keep my plan',
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(_advice!.detail, style: TextStyle(color: p.muted, height: 1.4)),
            const SizedBox(height: 8),
            Text('You decide — I\'ll budget for whatever you pick.',
                style: TextStyle(color: p.muted, fontStyle: FontStyle.italic, fontSize: 13)),
          ]),
        );
      default:
        return _QuestionStep(
          prompt: 'Which day of the month does it renew?',
          onBack: () => setState(() => _step = _advice == null ? 3 : 4),
          onNext: _submit,
          nextLabel: 'Add subscription',
          busy: _busy,
          child: Row(children: [
            Text('Day ', style: TextStyle(color: p.on)),
            DropdownButton<int>(
              value: _renewDay,
              items: [for (var d = 1; d <= 31; d++) DropdownMenuItem(value: d, child: Text('$d'))],
              onChanged: (v) => setState(() => _renewDay = v ?? _renewDay),
            ),
          ]),
        );
    }
  }
}

// --- "Something else" -> hand the free text to the advisor ------------------

class _OtherFlow extends StatelessWidget {
  const _OtherFlow({required this.onBack, this.text = ''});
  final VoidCallback onBack;

  /// What the user already typed on the hub, if they came in that way — carried
  /// through so they never have to say the same thing twice.
  final String text;

  @override
  Widget build(BuildContext context) {
    final p = AppColors.active;
    final hasText = text.trim().isNotEmpty;
    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 32),
      children: [
        Text(
          hasText ? "Let's talk that through" : "Tell me what you're planning",
          style: TextStyle(color: p.on, fontSize: 17, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 8),
        Text(
          hasText
              ? "That one's not a straight purchase, subscription or goal — so let's "
                  "just talk. I'll bring what you said with me."
              : "Anything from a wedding to a new laptop — just say it in your own words "
                  "and I'll take it from there.",
          style: TextStyle(color: p.muted, height: 1.4),
        ),
        if (hasText) ...[
          const SizedBox(height: 12),
          GlassCard(child: Text('"${text.trim()}"', style: TextStyle(color: p.on, fontStyle: FontStyle.italic))),
        ],
        const SizedBox(height: 20),
        // Expanded for the same reason as _QuestionStep: the theme's filled
        // buttons are full-width (minimumSize: Size.fromHeight(50)), so a bare
        // one in a Row gets an infinite tight width and silently fails layout.
        Row(children: [
          Expanded(child: OutlinedButton(onPressed: onBack, child: const Text('Back'))),
          const SizedBox(width: 12),
          Expanded(
            child: FilledButton.icon(
              icon: const Icon(Icons.chat_bubble_outline, size: 18),
              // The advisor already routes anything unusual through the engines
              // (and the LLM when reachable) — so "something else" is never a
              // dead end, just a different door into the same intelligence.
              onPressed: () => context.go(
                hasText ? '/advisor?ask=${Uri.encodeQueryComponent(text.trim())}' : '/advisor',
              ),
              label: const Text('Talk to Advary'),
            ),
          ),
        ]),
      ],
    );
  }
}

// --- shared bits ------------------------------------------------------------

class _DatePickerRow extends StatelessWidget {
  const _DatePickerRow({required this.value, required this.hint, required this.onPick});
  final DateTime? value;
  final String hint;
  final ValueChanged<DateTime?> onPick;

  @override
  Widget build(BuildContext context) {
    final p = AppColors.active;
    return Row(children: [
      Expanded(
        child: Text(
          value == null ? hint : '${value!.day}/${value!.month}/${value!.year}',
          style: TextStyle(color: value == null ? p.muted : p.on),
        ),
      ),
      TextButton.icon(
        icon: const Icon(Icons.calendar_today_outlined, size: 18),
        label: Text(value == null ? 'Pick' : 'Change'),
        onPressed: () async {
          final now = DateTime.now();
          final picked = await showDatePicker(
            context: context,
            initialDate: value ?? now.add(const Duration(days: 90)),
            firstDate: now,
            lastDate: DateTime(now.year + 10),
          );
          if (picked != null) onPick(picked);
        },
      ),
    ]);
  }
}

void _invalidatePlan(WidgetRef ref) {
  // A new goal/subscription changes the whole picture — refresh what feeds the
  // plan and the daily allowance so the change reflects across the app.
  ref.invalidate(realityProvider);
  ref.invalidate(feasibilityProvider);
  ref.invalidate(recommendationsProvider);
}
