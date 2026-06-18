import 'package:expensitor_mobile/core/auth/auth_state.dart';
import 'package:expensitor_mobile/core/format/dates.dart';
import 'package:expensitor_mobile/features/ledger/ledger_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('expenseBody', () {
    test('builds the required fields and formats the date', () {
      final body = expenseBody(
        amount: '250.50',
        currency: 'inr',
        date: DateTime(2026, 6, 9),
        categoryId: 'cat-1',
        description: 'Lunch',
      );
      expect(body, {
        'original_amount': '250.50',
        'original_currency': 'INR',
        'expense_date': '2026-06-09',
        'category_id': 'cat-1',
        'description': 'Lunch',
      });
    });

    test('omits category_id and description when empty/null', () {
      final body = expenseBody(
        amount: '10',
        currency: 'INR',
        date: DateTime(2026, 1, 1),
        categoryId: null,
        description: '   ',
      );
      expect(body.containsKey('category_id'), isFalse);
      expect(body.containsKey('description'), isFalse);
      expect(body['expense_date'], '2026-01-01');
    });
  });

  group('incomeBody', () {
    test('includes source_type and trims description', () {
      final body = incomeBody(
        sourceType: 'salary',
        amount: '50000',
        currency: 'INR',
        date: DateTime(2026, 6, 1),
        description: '  June pay  ',
      );
      expect(body['source_type'], 'salary');
      expect(body['received_date'], '2026-06-01');
      expect(body['description'], 'June pay');
    });

    test('omits blank description', () {
      final body = incomeBody(
        sourceType: 'gift', amount: '500', currency: 'INR', date: DateTime(2026, 6, 1));
      expect(body.containsKey('description'), isFalse);
    });
  });

  test('ymd zero-pads month and day', () {
    expect(ymd(DateTime(2026, 3, 7)), '2026-03-07');
  });

  test('incomeSourceLabel maps known + falls back to raw', () {
    expect(incomeSourceLabel('salary'), 'Salary');
    expect(incomeSourceLabel('freelance'), 'Freelance');
    expect(incomeSourceLabel('mystery'), 'mystery');
  });

  test('CategoryOption.fromJson', () {
    final c = CategoryOption.fromJson({'id': 'abc', 'name': 'Groceries', 'is_essential': true});
    expect(c.id, 'abc');
    expect(c.name, 'Groceries');
    expect(c.isEssential, isTrue);
  });

  group('Txn parsing', () {
    test('expense: debit, base currency, title falls back to "Expense"', () {
      final t = Txn.fromExpense({
        'converted_amount': '250.0000', 'base_currency': 'INR',
        'expense_date': '2026-06-09', 'created_at': '2026-06-09T10:00:00Z',
        'category_id': 'cat-1', 'description': null,
      });
      expect(t.isCredit, isFalse);
      expect(t.amount, '250.0000');
      expect(t.currency, 'INR');
      expect(t.title, 'Expense');
      expect(t.categoryId, 'cat-1');
    });

    test('income: credit, title falls back to source label', () {
      final t = Txn.fromIncome({
        'converted_amount': '50000.0000', 'base_currency': 'INR',
        'received_date': '2026-06-01', 'created_at': '2026-06-01T09:00:00Z',
        'source_type': 'salary', 'description': '',
      });
      expect(t.isCredit, isTrue);
      expect(t.title, 'Salary');
      expect(t.sourceLabel, 'Salary');
    });
  });

  test('mergeTransactions sorts newest-first by sortAt', () {
    final older = Txn.fromExpense({
      'converted_amount': '1', 'base_currency': 'INR',
      'expense_date': '2026-06-01', 'created_at': '2026-06-01T08:00:00Z',
    });
    final newer = Txn.fromIncome({
      'converted_amount': '2', 'base_currency': 'INR',
      'received_date': '2026-06-10', 'created_at': '2026-06-10T08:00:00Z',
      'source_type': 'bonus',
    });
    final merged = mergeTransactions([older], [newer]);
    expect(merged.first.isCredit, isTrue); // newer income first
    expect(merged.last.isCredit, isFalse);
  });

  group('eventBody', () {
    test('builds planned-expense body with occasion + notes', () {
      final body = eventBody(
        title: '  Outing  ',
        amount: '1500',
        currency: 'inr',
        date: DateTime(2026, 9, 27),
        occasionType: 'outing',
        notes: '  with friends  ',
      );
      expect(body, {
        'title': 'Outing',
        'planned_date': '2026-09-27',
        'original_amount': '1500',
        'original_currency': 'INR',
        'occasion_type': 'outing',
        'notes': 'with friends',
      });
    });

    test('omits occasion + notes when empty', () {
      final body = eventBody(title: 'Trip', amount: '900', currency: 'INR', date: DateTime(2026, 1, 1));
      expect(body.containsKey('occasion_type'), isFalse);
      expect(body.containsKey('notes'), isFalse);
    });
  });

  group('resolveRedirect covers the V2 routes', () {
    test('authenticated stays on every V2 route (no redirect)', () {
      for (final loc in [
        '/home', '/plan-today', '/budget-setup', '/advisor', '/convert', '/feedback',
        '/contact', '/date/2026-06-17', '/date/2026-06-17/add-expense',
      ]) {
        expect(resolveRedirect(status: AuthStatus.authenticated, location: loc), isNull, reason: loc);
      }
    });

    test('unauthenticated is bounced to login from any route', () {
      expect(resolveRedirect(status: AuthStatus.unauthenticated, location: '/home'), '/login');
      expect(resolveRedirect(status: AuthStatus.unauthenticated, location: '/date/2026-06-17'), '/login');
    });
  });
}
