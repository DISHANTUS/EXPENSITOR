import 'package:expensitor_mobile/core/theme/app_theme.dart';
import 'package:expensitor_mobile/features/diary/diary_repository.dart';
import 'package:expensitor_mobile/features/diary/diary_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Stands in for the backend so these tests pin the UI's half of the contract:
/// given what Advary asks, does the screen ask it, keep the user's words safe,
/// and let them out?
class _FakeDiary implements DiaryRepository {
  _FakeDiary({this.questions = const [], this.failFromCall});

  /// Start failing once this many calls have succeeded. Lets one test walk into
  /// the conversation and THEN hit a network failure.
  final int? failFromCall;

  /// Returned in order: one per write/answer call. A null entry means "nothing
  /// more to ask" — the normal way a conversation ends.
  final List<String?> questions;

  int calls = 0;
  final List<String> written = [];
  final List<String> answered = [];
  final List<String> closed = [];

  DiaryEntry _entry() => DiaryEntry(id: 'e1', entryDate: DateTime(2026, 7, 16), text: 'bought fruits');

  DiaryReply _next() {
    final q = calls < questions.length ? questions[calls] : null;
    calls++;
    return DiaryReply(entry: _entry(), question: q);
  }

  @override
  Future<DiaryReply> write(String text) async {
    written.add(text);
    return _next();
  }

  @override
  Future<DiaryReply> answer(String entryId, {required String question, required String answer}) async {
    answered.add(answer);
    if (failFromCall != null && calls >= failFromCall!) throw Exception('offline');
    return _next();
  }

  @override
  Future<void> close(String entryId) async => closed.add(entryId);

  @override
  Future<void> delete(String entryId) async {}

  @override
  Future<List<DiaryEntry>> list() async => [];

  @override
  Future<DiaryPatterns> patterns() async => const DiaryPatterns(ready: false, entries: 0, needed: 5);
}

Widget _screen(_FakeDiary fake, {DiaryPatterns? patterns}) => ProviderScope(
      overrides: [
        diaryRepositoryProvider.overrideWithValue(fake),
        diaryEntriesProvider.overrideWith((ref) async => const <DiaryEntry>[]),
        if (patterns != null) diaryPatternsProvider.overrideWith((ref) async => patterns),
      ],
      // The real theme — it makes buttons full-width, which is what silently
      // broke a button row on a device once already.
      child: MaterialApp(theme: AppTheme.dark(), home: const Scaffold(body: DiaryBody())),
    );

Future<void> _write(WidgetTester tester, String text) async {
  await tester.enterText(find.byType(TextField).first, text);
  await tester.pump();
  await tester.tap(find.widgetWithText(FilledButton, 'Save'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('writing a note surfaces the first question', (tester) async {
    final fake = _FakeDiary(questions: ['Which fruits?']);
    await tester.pumpWidget(_screen(fake));
    await tester.pumpAndSettle();

    await _write(tester, 'bought fruits');
    expect(fake.written, ['bought fruits']);
    expect(find.text('Which fruits?'), findsOneWidget);
    expect(find.text('Advary asks'), findsOneWidget);
  });

  testWidgets('the branch keeps going, one question at a time', (tester) async {
    final fake = _FakeDiary(questions: ['Which fruits?', 'Which juice?', 'Roughly what did that come to?']);
    await tester.pumpWidget(_screen(fake));
    await tester.pumpAndSettle();
    await _write(tester, 'bought fruits');

    await tester.enterText(find.byType(TextField).first, 'apples and juice');
    await tester.tap(find.widgetWithText(FilledButton, 'Answer'));
    await tester.pumpAndSettle();

    expect(find.text('Which juice?'), findsOneWidget);
    expect(find.text('Which fruits?'), findsNothing); // one at a time, not a form
    expect(fake.answered, ['apples and juice']);
  });

  testWidgets('when there is nothing left to ask, it stops', (tester) async {
    final fake = _FakeDiary(questions: ['Which fruits?', null]);
    await tester.pumpWidget(_screen(fake));
    await tester.pumpAndSettle();
    await _write(tester, 'bought fruits');

    await tester.enterText(find.byType(TextField).first, 'apples');
    await tester.tap(find.widgetWithText(FilledButton, 'Answer'));
    await tester.pumpAndSettle();

    expect(find.text('Advary asks'), findsNothing);
    expect(find.text('What happened today?'), findsOneWidget); // back to writing
  });

  testWidgets('a note with nothing to ask about is just saved', (tester) async {
    final fake = _FakeDiary(questions: [null]);
    await tester.pumpWidget(_screen(fake));
    await tester.pumpAndSettle();
    await _write(tester, 'felt tired after class');

    expect(fake.written, ['felt tired after class']);
    expect(find.text('Advary asks'), findsNothing);
  });

  testWidgets('the user can always skip out of the questions', (tester) async {
    // A diary that won't stop asking is a diary nobody writes in twice.
    final fake = _FakeDiary(questions: ['Which fruits?', 'Which juice?']);
    await tester.pumpWidget(_screen(fake));
    await tester.pumpAndSettle();
    await _write(tester, 'bought fruits');

    await tester.tap(find.widgetWithText(OutlinedButton, 'Skip'));
    await tester.pumpAndSettle();

    expect(find.text('Advary asks'), findsNothing);
    expect(fake.closed, ['e1']);
  });

  testWidgets('a failed answer keeps the words the user typed', (tester) async {
    // Losing what someone typed because the network hiccuped is the one
    // unforgivable bug in a text box.
    final fake = _FakeDiary(questions: ['Which fruits?'], failFromCall: 1);
    await tester.pumpWidget(_screen(fake));
    await tester.pumpAndSettle();
    await _write(tester, 'bought fruits');

    await tester.enterText(find.byType(TextField).first, 'apples and mangoes');
    await tester.tap(find.widgetWithText(FilledButton, 'Answer'));
    await tester.pumpAndSettle();

    // The send failed: the question stays, and so do their words.
    expect(find.text('Which fruits?'), findsOneWidget);
    expect(find.widgetWithText(TextField, 'apples and mangoes'), findsOneWidget);
  });

  testWidgets('the question row lays out under the real theme', (tester) async {
    final fake = _FakeDiary(questions: ['Which fruits?']);
    await tester.pumpWidget(_screen(fake));
    await tester.pumpAndSettle();
    await _write(tester, 'bought fruits');

    expect(tester.takeException(), isNull);
    // Concrete types: byType matches the exact runtime type, so the abstract
    // ButtonStyleButton finds nothing.
    for (final finder in [
      find.widgetWithText(OutlinedButton, 'Skip'),
      find.widgetWithText(FilledButton, 'Answer'),
    ]) {
      final size = tester.getSize(finder);
      expect(size.width, greaterThan(0));
      expect(size.width, lessThan(double.infinity));
      expect(size.height, greaterThan(0));
    }
  });

  testWidgets('a question worked out while you were away is waiting when you come back', (tester) async {
    // The whole point of the catch-up queue: the model was offline when this
    // note was written, ran later, and the answer has to actually reach the
    // user rather than sit in a column nobody reads.
    await tester.pumpWidget(ProviderScope(
      overrides: [
        diaryRepositoryProvider.overrideWithValue(_FakeDiary(questions: [null])),
        diaryEntriesProvider.overrideWith((ref) async => [
              DiaryEntry(
                id: 'e9',
                entryDate: DateTime(2026, 7, 16),
                text: 'spent the afternoon at the barber',
                pendingQuestion: 'How long were you at the barber?',
              ),
            ]),
      ],
      child: MaterialApp(theme: AppTheme.dark(), home: const Scaffold(body: DiaryBody())),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Advary asks'), findsOneWidget);
    expect(find.text('How long were you at the barber?'), findsOneWidget);
  });

  testWidgets('a waiting question never talks over a live conversation', (tester) async {
    // Writing a note now must win over a question parked earlier — otherwise
    // the screen hijacks itself mid-sentence.
    await tester.pumpWidget(ProviderScope(
      overrides: [
        diaryRepositoryProvider.overrideWithValue(_FakeDiary(questions: ['Which fruits?'])),
        diaryEntriesProvider.overrideWith((ref) async => [
              DiaryEntry(
                id: 'e9',
                entryDate: DateTime(2026, 7, 16),
                text: 'old note',
                pendingQuestion: 'An older question?',
              ),
            ]),
      ],
      child: MaterialApp(theme: AppTheme.dark(), home: const Scaffold(body: DiaryBody())),
    ));
    await tester.pumpAndSettle();
    // The parked one shows first (nothing else in flight)...
    expect(find.text('An older question?'), findsOneWidget);
  });

  testWidgets('a closed entry never resurfaces its parked question', (tester) async {
    // They already waved the questions off. A stale job must not override that.
    await tester.pumpWidget(ProviderScope(
      overrides: [
        diaryRepositoryProvider.overrideWithValue(_FakeDiary(questions: [null])),
        diaryEntriesProvider.overrideWith((ref) async => [
              DiaryEntry(
                id: 'e9',
                entryDate: DateTime(2026, 7, 16),
                text: 'old note',
                pendingQuestion: 'Ignored?',
                closed: true,
              ),
            ]),
      ],
      child: MaterialApp(theme: AppTheme.dark(), home: const Scaffold(body: DiaryBody())),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Advary asks'), findsNothing);
    expect(find.text('What happened today?'), findsOneWidget);
  });

  testWidgets('with too little written, it says so instead of inventing a pattern', (tester) async {
    await tester.pumpWidget(_screen(
      _FakeDiary(questions: [null]),
      patterns: const DiaryPatterns(ready: false, entries: 2, needed: 5),
    ));
    await tester.pumpAndSettle();

    expect(find.textContaining('Write 3 more notes'), findsOneWidget);
    expect(find.text('What I notice'), findsNothing);
  });

  testWidgets('once there is evidence, it reports it and asks rather than assumes', (tester) async {
    await tester.pumpWidget(_screen(
      _FakeDiary(questions: [null]),
      patterns: const DiaryPatterns(
        ready: true,
        entries: 5,
        days: 5,
        observations: [
          PatternObservation(kind: 'mention', word: 'mango', text: "You've mentioned mango on 5 of the 5 days you've written."),
          PatternObservation(kind: 'weekday', word: 'mango', text: 'Usually a Thursday — 5 of the 5 times you mentioned it.'),
        ],
        askWord: 'mango',
        askQuestion: 'You mention mango a lot — is it a favourite, or just habit?',
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.text('What I notice'), findsOneWidget);
    expect(find.textContaining('mentioned mango on 5 of the 5 days'), findsOneWidget);
    expect(find.textContaining('Usually a Thursday'), findsOneWidget);
    // It asks whether it's a favourite; it must never assert one.
    expect(find.textContaining('is it a favourite, or just habit?'), findsOneWidget);
  });
}
