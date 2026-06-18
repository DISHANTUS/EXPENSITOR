import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import 'ledger_models.dart';

/// Writes expenses/incomes and reads the merged transaction history. No mocks.
class LedgerRepository {
  LedgerRepository(this._dio);
  final Dio _dio;

  Future<void> createExpense({
    required String amount,
    required String currency,
    required DateTime date,
    String? categoryId,
    String? description,
  }) =>
      _post('/expenses', expenseBody(
        amount: amount,
        currency: currency,
        date: date,
        categoryId: categoryId,
        description: description,
      ));

  Future<void> createIncome({
    required String sourceType,
    required String amount,
    required String currency,
    required DateTime date,
    String? description,
  }) =>
      _post('/incomes', incomeBody(
        sourceType: sourceType,
        amount: amount,
        currency: currency,
        date: date,
        description: description,
      ));

  Future<void> createEvent({
    required String title,
    required String amount,
    required String currency,
    required DateTime date,
    String? occasionType,
    String? notes,
  }) =>
      _post('/planned-expenses', eventBody(
        title: title,
        amount: amount,
        currency: currency,
        date: date,
        occasionType: occasionType,
        notes: notes,
      ));

  Future<List<CategoryOption>> categories() async {
    try {
      final res = await _dio.get<dynamic>('/categories');
      final list = (res.data as List?) ?? const [];
      return list
          .whereType<Map>()
          .map((e) => CategoryOption.fromJson(e.cast<String, dynamic>()))
          .toList();
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<List<Txn>> recentTransactions({int limit = 50}) async {
    final results = await Future.wait([
      _listTxns('/expenses', Txn.fromExpense, limit),
      _listTxns('/incomes', Txn.fromIncome, limit),
    ]);
    return mergeTransactions(results[0], results[1]);
  }

  Future<List<Txn>> _listTxns(
    String path,
    Txn Function(Map<String, dynamic>) parse,
    int limit,
  ) async {
    try {
      final res = await _dio.get<dynamic>(path, queryParameters: {'limit': limit});
      final items = ((res.data as Map)['items'] as List?) ?? const [];
      return items
          .whereType<Map>()
          .map((e) => parse(e.cast<String, dynamic>()))
          .toList();
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<void> _post(String path, Map<String, dynamic> body) async {
    try {
      await _dio.post<dynamic>(path, data: body);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final ledgerRepositoryProvider =
    Provider<LedgerRepository>((ref) => LedgerRepository(ref.watch(dioProvider)));

final categoriesProvider = FutureProvider.autoDispose<List<CategoryOption>>(
    (ref) => ref.watch(ledgerRepositoryProvider).categories());

final recentTransactionsProvider = FutureProvider.autoDispose<List<Txn>>(
    (ref) => ref.watch(ledgerRepositoryProvider).recentTransactions());
