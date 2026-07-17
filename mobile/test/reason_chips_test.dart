import 'package:expensitor_mobile/core/settings/settings_repository.dart';
import 'package:expensitor_mobile/features/ledger/add_expense_screen.dart';
import 'package:expensitor_mobile/features/ledger/ledger_models.dart';
import 'package:expensitor_mobile/features/ledger/ledger_repository.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

/// A stand-in ledger repo: the only method these tests exercise is the reason
/// lookup. Everything else is a no-op, so the screen mounts without a network.
class _FakeLedger implements LedgerRepository {
  _FakeLedger(this._reasons);
  final List<String> _reasons;
  String? lastAmount;

  @override
  Future<List<String>> reasonSuggestions({String? amount, DateTime? date, String? categoryId}) async {
    lastAmount = amount;
    return _reasons;
  }

  @override
  dynamic noSuchMethod(Invocation _) => throw UnimplementedError();
}

Widget _screen(_FakeLedger fake) => ProviderScope(
      overrides: [
        ledgerRepositoryProvider.overrideWithValue(fake),
        categoriesProvider.overrideWith((ref) async => const <CategoryOption>[]),
        userSettingsProvider.overrideWith((ref) async => const UserSettings(baseCurrency: 'INR')),
      ],
      child: MaterialApp.router(
        routerConfig: GoRouter(routes: [
          GoRoute(path: '/', builder: (_, __) => AddExpenseScreen(date: DateTime(2026, 7, 16))),
        ]),
      ),
    );

void main() {
  testWidgets('reasons the user gave before show as one-tap chips', (tester) async {
    await tester.pumpWidget(_screen(_FakeLedger(['chai', 'bus', 'lunch'])));
    await tester.pumpAndSettle();

    expect(find.text('What was this for?'), findsOneWidget);
    for (final r in ['chai', 'bus', 'lunch']) {
      expect(find.widgetWithText(ActionChip, r), findsOneWidget);
    }
  });

  testWidgets('tapping a chip fills the notes field', (tester) async {
    await tester.pumpWidget(_screen(_FakeLedger(['chai', 'bus'])));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(ActionChip, 'chai'));
    await tester.pumpAndSettle();

    // The notes field now holds the tapped reason — a repeat spend is a tap.
    expect(find.widgetWithText(TextFormField, 'chai'), findsOneWidget);
  });

  testWidgets('a fresh account with no history shows no chips, just the box', (tester) async {
    await tester.pumpWidget(_screen(_FakeLedger(const [])));
    await tester.pumpAndSettle();

    expect(find.text('What was this for?'), findsNothing);
    expect(find.byType(ActionChip), findsNothing);
    // The plain notes field is still there — suggestions are a bonus, not a gate.
    expect(find.widgetWithText(TextFormField, 'Notes (optional)'), findsOneWidget);
  });

  testWidgets('typing an amount re-ranks against that amount', (tester) async {
    final fake = _FakeLedger(['chai']);
    await tester.pumpWidget(_screen(fake));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField).first, '50');
    // Debounced (~350ms) — let it fire.
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();

    expect(fake.lastAmount, '50', reason: 'the amount typed should drive the ranking query');
  });
}
