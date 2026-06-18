import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../companion/reaction.dart';
import '../companion/reaction_queue.dart';
import '../onboarding/tour_controller.dart';
import 'stt_service.dart';
import 'voice_plan.dart';
import 'voice_repository.dart';
import 'voice_service.dart';

/// Where we are in a spoken exchange: tap mic → listening → thinking → speaking.
enum ConvPhase { idle, listening, thinking, speaking, unavailable, error }

class ConversationState {
  const ConversationState({
    this.phase = ConvPhase.idle,
    this.active = false,
    this.transcript = '',
    this.reply = '',
    this.navigate,
  });

  final ConvPhase phase;
  final bool active;
  final String transcript;
  final String reply;
  final String? navigate;

  ConversationState copyWith({
    ConvPhase? phase,
    bool? active,
    String? transcript,
    String? reply,
    Object? navigate = _unset,
  }) =>
      ConversationState(
        phase: phase ?? this.phase,
        active: active ?? this.active,
        transcript: transcript ?? this.transcript,
        reply: reply ?? this.reply,
        navigate: navigate == _unset ? this.navigate : navigate as String?,
      );

  static const _unset = Object();
}

// Spoken-write intent → 5a.5 reaction kind (the ack shown after a voice write).
const _kindForAction = {
  'add_expense': 'expense', 'add_income': 'income', 'add_receivable': 'lent',
  'mark_receivable_received': 'loan_repaid', 'move_event': 'event',
  'create_savings_goal': 'goal', 'change_savings_target': 'goal',
};

final _yes = RegExp(r'\b(yes|yeah|yep|yup|sure|go ahead|do it|confirm|okay|ok|please)\b', caseSensitive: false);
final _no = RegExp(r"\b(no|nope|cancel|stop|nah|never ?mind|don'?t)\b", caseSensitive: false);

/// Orchestrates one spoken turn and the multi-turn write flow (slot-fill +
/// confirm + correction). Reuses the 5b [VoiceController] to speak replies.
class ConversationController extends StateNotifier<ConversationState> {
  ConversationController(this._stt, this._voice, this._repo, {this.onWriteResult, this.onTour})
      : super(const ConversationState());

  final SttEngine _stt;
  final VoiceController _voice;
  final VoiceRepository _repo;
  final void Function(String action)? onWriteResult;   // → fire the reaction ack
  final void Function()? onTour;                        // "show me around" → launch the tour

  Map<String, dynamic>? _session;        // query follow-up memory
  // Write-flow state:
  String? _commandText;
  final Map<String, String> _answers = {};
  String? _requestId;
  String? _awaiting;                     // slot the next utterance fills
  bool _confirming = false;              // awaiting a yes/no
  bool _submitted = false;

  void _resetWrite() {
    _commandText = null;
    _answers.clear();
    _requestId = null;
    _awaiting = null;
    _confirming = false;
  }

  Future<void> open() async {
    _resetWrite();
    state = state.copyWith(active: true, reply: '', transcript: '', navigate: null);
    await _listen();
  }

  Future<void> _listen() async {
    await _voice.stop();
    final ok = await _stt.initialize();
    if (!ok) {
      state = state.copyWith(
          phase: ConvPhase.unavailable, reply: 'Voice input isn’t available on this device.');
      return;
    }
    _submitted = false;
    state = state.copyWith(phase: ConvPhase.listening, transcript: '');
    await _stt.listen(
      onResult: (text, isFinal) {
        if (state.phase != ConvPhase.listening) return;
        state = state.copyWith(transcript: text);
        if (isFinal) _handle(text);
      },
      onDone: () {
        if (_submitted || state.phase != ConvPhase.listening) return;
        final t = state.transcript.trim();
        if (t.isNotEmpty) {
          _handle(t);
        } else {
          state = state.copyWith(phase: ConvPhase.idle);
        }
      },
    );
  }

  Future<void> _say(String line) async {
    state = state.copyWith(phase: ConvPhase.speaking, reply: line);
    await _voice.speakPlan(VoicePlan(deterministicSegments: [line]));
  }

  Future<void> _handle(String utterance) async {
    if (_submitted) return;
    _submitted = true;
    await _stt.stop();
    final u = utterance.trim();
    if (u.isEmpty) {
      state = state.copyWith(phase: ConvPhase.idle);
      return;
    }
    state = state.copyWith(phase: ConvPhase.thinking, transcript: u);

    var confirm = false;
    if (_awaiting != null) {
      _answers[_awaiting!] = u;          // this utterance answers the open slot
      _awaiting = null;
    } else if (_confirming) {
      if (_no.hasMatch(u)) {
        _resetWrite();
        await _say('Okay, cancelled.');
        if (mounted) state = state.copyWith(phase: ConvPhase.idle);
        return;
      }
      if (_yes.hasMatch(u)) {
        confirm = true;
        _confirming = false;
      } else {
        await _say('Sorry — should I go ahead? Yes or no.');
        if (mounted) await _listen();
        return;
      }
    }

    try {
      final out = await _repo.ask(
        _commandText ?? u,
        session: _session,
        commandText: _commandText,
        answers: _answers,
        confirm: confirm,
        requestId: _requestId,
      );
      _session = out.session ?? _session;
      if (out.commandText != null) _commandText = out.commandText;
      if (out.requestId != null) _requestId = out.requestId;

      state = state.copyWith(phase: ConvPhase.speaking, reply: out.speech, navigate: out.navigate);
      await _voice.speakPlan(out.voice);
      if (!mounted) return;

      if (out.awaiting != null) {                       // need a slot → ask + listen
        _awaiting = out.awaiting;
        await _listen();
        return;
      }
      if (out.requiresConfirmation) {                   // preview → listen for yes/no
        _confirming = true;
        await _listen();
        return;
      }
      if (out.type == 'tour') {                          // "show me around" → run the tour
        onTour?.call();
        _resetWrite();
      } else if (out.type == 'result') {
        if (out.action != null) onWriteResult?.call(out.action!);   // reaction ack
        _resetWrite();
      } else if (out.wantsFollowUp) {                   // chat clarify / check-in
        await _listen();
        return;
      } else {
        _resetWrite();
      }
      state = state.copyWith(phase: ConvPhase.idle);
    } catch (_) {
      if (mounted) {
        state = state.copyWith(
            phase: ConvPhase.error, reply: 'Sorry, I couldn’t reach the advisor. Try again.');
      }
    }
  }

  Future<void> listenAgain() => _listen();

  Future<void> stop() async {
    _submitted = true;
    await _stt.cancel();
    await _voice.stop();
    if (mounted) state = state.copyWith(phase: ConvPhase.idle);
  }

  Future<void> close() async {
    await stop();
    _resetWrite();
    if (mounted) state = state.copyWith(active: false);
  }
}

final conversationControllerProvider =
    StateNotifierProvider<ConversationController, ConversationState>((ref) => ConversationController(
          ref.watch(sttEngineProvider),
          ref.watch(voiceControllerProvider.notifier),
          ref.watch(voiceRepositoryProvider),
          onWriteResult: (action) {
            final kind = _kindForAction[action];
            if (kind != null) ref.read(reactionQueueProvider.notifier).push(reactionFor(kind));
          },
          onTour: () => ref.read(tourControllerProvider.notifier).start(),
        ));
