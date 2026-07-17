import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';

/// A transaction read out of a bank SMS, awaiting the user's confirmation.
///
/// This is the "connect to UPI" path: there's no API to read GPay/PhonePe, but
/// every UPI payment makes the bank text you, and that text is provider-
/// agnostic. The parse is deliberately a *candidate* — nothing is recorded until
/// the user taps a reason, because SMS parsing has false positives and a phantom
/// expense erodes trust faster than a missed one.
class TxnCandidate {
  const TxnCandidate({
    required this.kind,
    required this.amount,
    required this.raw,
    this.merchant,
    this.isUpi = false,
    this.suggestedReason,
    this.reasons = const [],
  });

  factory TxnCandidate.fromJson(Map<String, dynamic> j) => TxnCandidate(
        kind: (j['kind'] ?? 'expense').toString(),
        amount: (j['amount'] ?? '0').toString(),
        merchant: j['merchant'] as String?,
        isUpi: j['is_upi'] == true,
        suggestedReason: j['suggested_reason'] as String?,
        // The user's OWN learned reasons, ranked for this amount. Never another
        // user's, never invented.
        reasons: [for (final r in (j['reasons'] as List? ?? const [])) r.toString()],
        raw: (j['raw'] ?? '').toString(),
      );

  final String kind; // expense | income
  final String amount;
  final String? merchant;
  final bool isUpi;
  final String? suggestedReason;
  final List<String> reasons;
  final String raw;

  bool get isExpense => kind == 'expense';
}

class TransactionCaptureRepository {
  TransactionCaptureRepository(this._dio);
  final Dio _dio;

  /// Read a bank SMS into a candidate, or null when it isn't a transaction we
  /// act on — which is the common, correct outcome for most texts.
  Future<TxnCandidate?> parseSms(String text) async {
    try {
      final res = await _dio.post<dynamic>('/transactions/parse-sms', data: {'text': text});
      final cand = (res.data as Map)['candidate'];
      return cand == null ? null : TxnCandidate.fromJson(Map<String, dynamic>.from(cand as Map));
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final transactionCaptureRepositoryProvider = Provider<TransactionCaptureRepository>(
    (ref) => TransactionCaptureRepository(ref.watch(dioProvider)));
