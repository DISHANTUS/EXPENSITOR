import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';

/// A learned daily habit the compact Home offers to confirm in one tap
/// ("Is the ₹200 for travel over?"). Predicted server-side from history only;
/// nothing exists until the user confirms, which is a normal expense POST.
class PredictedExpense {
  const PredictedExpense({
    required this.categoryId,
    required this.label,
    required this.amount,
    required this.dayType,
    required this.confidence,
  });

  factory PredictedExpense.fromJson(Map<String, dynamic> j) => PredictedExpense(
        categoryId: (j['category_id'] ?? '').toString(),
        label: (j['label'] ?? '').toString(),
        amount: (j['amount'] as num?)?.toDouble() ?? 0,
        dayType: (j['day_type'] ?? 'weekday').toString(),
        confidence: (j['confidence'] ?? 'medium').toString(),
      );

  final String categoryId;
  final String label;
  final double amount;
  final String dayType;
  final String confidence;
}

class PredictedExpenseRepository {
  PredictedExpenseRepository(this._dio);
  final Dio _dio;

  Future<List<PredictedExpense>> predictedToday() async {
    try {
      final res = await _dio.get<dynamic>('/expenses/predicted-today');
      return ((res.data as List?) ?? const [])
          .whereType<Map>()
          .map((e) => PredictedExpense.fromJson(e.cast<String, dynamic>()))
          .toList();
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Confirm a habit — [amount] may differ from the prediction when the user
  /// corrects it ("amount change"). This is the ONLY thing that writes money
  /// data; a prediction alone never does. Dated to the device's today, since
  /// this is confirming spending that happened today.
  Future<void> confirm({required String categoryId, required double amount, required String currency}) async {
    try {
      final now = DateTime.now();
      final today = '${now.year.toString().padLeft(4, '0')}-'
          '${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
      await _dio.post<dynamic>('/expenses', data: {
        'original_amount': amount.toString(),
        'original_currency': currency,
        'expense_date': today,
        'category_id': categoryId,
      });
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final predictedExpenseRepositoryProvider =
    Provider<PredictedExpenseRepository>((ref) => PredictedExpenseRepository(ref.watch(dioProvider)));

final predictedTodayProvider = FutureProvider.autoDispose<List<PredictedExpense>>(
    (ref) => ref.watch(predictedExpenseRepositoryProvider).predictedToday());
