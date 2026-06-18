import 'package:dio/dio.dart';
import 'package:expensitor_mobile/core/voice/conversation_controller.dart';
import 'package:expensitor_mobile/core/voice/stt_service.dart';
import 'package:expensitor_mobile/core/voice/voice_plan.dart';
import 'package:expensitor_mobile/core/voice/voice_repository.dart';
import 'package:expensitor_mobile/core/voice/voice_service.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeStt implements SttEngine {
  bool available = true;
  void Function(String, bool)? _onResult;
  void Function()? _onDone;

  @override
  bool get isAvailable => available;
  @override
  Future<bool> initialize() async => available;
  @override
  Future<void> listen({required void Function(String, bool) onResult, void Function()? onDone}) async {
    _onResult = onResult;
    _onDone = onDone;
  }

  @override
  Future<void> stop() async {}
  @override
  Future<void> cancel() async {}

  void emit(String text, bool isFinal) => _onResult?.call(text, isFinal);
  void done() => _onDone?.call();
}

class NoopTts implements TtsEngine {
  @override
  Future<void> configure() async {}
  @override
  Future<void> setStyle({required double rate, required double pitch, double volume = 1.0}) async {}
  @override
  Future<void> speak(String text) async {}
  @override
  Future<void> stop() async {}
  @override
  set onComplete(void Function()? cb) {}
  @override
  set onCancel(void Function()? cb) {}
}

class FakeRepo extends VoiceRepository {
  FakeRepo(this.replies) : super(Dio());
  final List<VoiceReply> replies;
  final List<String> asked = [];
  final List<Map<String, dynamic>?> sessions = [];
  final List<Map<String, String>?> answersLog = [];
  final List<bool> confirms = [];
  int _i = 0;

  @override
  Future<VoiceReply> ask(String text,
      {Map<String, dynamic>? session,
      String? commandText,
      Map<String, String>? answers,
      bool confirm = false,
      String? requestId}) async {
    asked.add(commandText ?? text);
    sessions.add(session);
    answersLog.add(answers == null ? null : Map.of(answers));
    confirms.add(confirm);
    return replies[_i++ % replies.length];
  }
}

VoiceReply _reply(String type, String speech, {Map<String, dynamic>? session}) => VoiceReply(
      type: type, speech: speech, session: session,
      voice: VoicePlan(deterministicSegments: [speech]),
    );

VoiceReply _clar(String field, String prompt, String command) => VoiceReply(
      type: 'clarification', speech: prompt, awaiting: field, commandText: command, requestId: 'rid1',
      voice: VoicePlan(deterministicSegments: [prompt]),
    );

VoiceReply _preview(String summary, String command, String action) => VoiceReply(
      type: 'preview', speech: summary, requiresConfirmation: true, commandText: command,
      requestId: 'rid1', action: action, voice: VoicePlan(deterministicSegments: [summary]),
    );

VoiceReply _result(String speech, String action) => VoiceReply(
      type: 'result', speech: speech, action: action, voice: VoicePlan(deterministicSegments: [speech]),
    );

Future<void> _settle() async {
  for (var i = 0; i < 12; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  test('open → listening; final transcript → asks and speaks the reply', () async {
    final stt = FakeStt();
    final repo = FakeRepo([_reply('drilldown', 'You had 3 red days.')]);
    final c = ConversationController(stt, VoiceController(NoopTts()), repo);

    await c.open();
    expect(c.state.phase, ConvPhase.listening);
    stt.emit('show my red days', true);
    await _settle();

    expect(repo.asked.single, 'show my red days');
    expect(c.state.reply, 'You had 3 red days.');
    expect(c.state.phase, ConvPhase.idle);
  });

  test('clarify reply re-listens, then completes (correction loop)', () async {
    final stt = FakeStt();
    final repo = FakeRepo([
      _reply('clarify', 'Which report would you like?'),
      _reply('report', 'You spent about 5,000 rupees.'),
    ]);
    final c = ConversationController(stt, VoiceController(NoopTts()), repo);

    await c.open();
    stt.emit('report', true);
    await _settle();
    expect(c.state.phase, ConvPhase.listening);          // clarify → asking again

    stt.emit('this month', true);
    await _settle();
    expect(repo.asked, ['report', 'this month']);
    expect(c.state.reply, 'You spent about 5,000 rupees.');
    expect(c.state.phase, ConvPhase.idle);
  });

  test('session is echoed back on the next turn', () async {
    final stt = FakeStt();
    final repo = FakeRepo([
      _reply('advisory', 'I’m a little concerned.', session: {'last_explain_ref': 'mood:current'}),
      _reply('advisory', 'Because two repayments are overdue.'),
    ]);
    final c = ConversationController(stt, VoiceController(NoopTts()), repo);

    await c.open();
    stt.emit('why are you worried', true);
    await _settle();
    await c.open();                                       // a second exchange
    stt.emit('why', true);
    await _settle();

    expect(repo.sessions.last, {'last_explain_ref': 'mood:current'});
  });

  test('unavailable recognizer surfaces a graceful state', () async {
    final stt = FakeStt()..available = false;
    final c = ConversationController(stt, VoiceController(NoopTts()), FakeRepo([_reply('answer', 'x')]));
    await c.open();
    expect(c.state.phase, ConvPhase.unavailable);
  });

  test('silence (done with no words) returns to idle without asking', () async {
    final stt = FakeStt();
    final repo = FakeRepo([_reply('answer', 'x')]);
    final c = ConversationController(stt, VoiceController(NoopTts()), repo);
    await c.open();
    stt.done();
    await _settle();
    expect(c.state.phase, ConvPhase.idle);
    expect(repo.asked, isEmpty);
  });

  group('write flow (5c-B)', () {
    test('expense: clarify category → preview → confirm → result + reaction ack', () async {
      final stt = FakeStt();
      final repo = FakeRepo([
        _clar('category', 'What category was it?', 'I spent 2000 today'),
        _preview('Add a ₹2,000 expense (Food & Dining). Should I go ahead?', 'I spent 2000 today', 'add_expense'),
        _result('₹2,000 expense added (Food & Dining).', 'add_expense'),
      ]);
      final acks = <String>[];
      final c = ConversationController(stt, VoiceController(NoopTts()), repo, onWriteResult: acks.add);

      await c.open();
      stt.emit('I spent 2000 today', true);
      await _settle();
      expect(c.state.reply, 'What category was it?');
      expect(c.state.phase, ConvPhase.listening);          // awaiting the slot

      stt.emit('food', true);
      await _settle();
      expect(c.state.reply, contains('Should I go ahead?'));
      expect(repo.answersLog.last, {'category': 'food'});   // slot accumulated

      stt.emit('yes', true);
      await _settle();
      expect(repo.confirms.last, isTrue);
      expect(repo.asked.last, 'I spent 2000 today');        // original command resent
      expect(c.state.reply, '₹2,000 expense added (Food & Dining).');
      expect(acks, ['add_expense']);                        // reaction ack fired
      expect(c.state.phase, ConvPhase.idle);
    });

    test('saying "no" at confirm cancels without executing', () async {
      final stt = FakeStt();
      final repo = FakeRepo([
        _preview('Record ₹10,000 income. Should I go ahead?', 'father gave me 10000', 'add_income'),
        _result('should not reach', 'add_income'),
      ]);
      final acks = <String>[];
      final c = ConversationController(stt, VoiceController(NoopTts()), repo, onWriteResult: acks.add);

      await c.open();
      stt.emit('my father gave me 10000', true);
      await _settle();
      expect(c.state.reply, contains('Should I go ahead?'));

      stt.emit('no', true);
      await _settle();
      expect(c.state.reply, 'Okay, cancelled.');
      expect(acks, isEmpty);                                // nothing executed
      expect(repo.confirms, everyElement(isFalse));
      expect(c.state.phase, ConvPhase.idle);
    });
  });
}
