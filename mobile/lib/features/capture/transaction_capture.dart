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

/// One line off a scanned receipt: what it cost on this bill, and what the user
/// usually pays (when they've bought it before).
class ReceiptLine {
  const ReceiptLine({required this.name, required this.price, this.typicalPrice, this.observations});
  factory ReceiptLine.fromJson(Map<String, dynamic> j) => ReceiptLine(
        name: (j['name'] ?? '').toString(),
        price: (j['price'] ?? '').toString(),
        typicalPrice: j['typical_price'] as String?,
        observations: (j['observations'] as num?)?.toInt(),
      );
  final String name;
  final String price;
  final String? typicalPrice; // "you usually pay ₹58", null when no history
  final int? observations;

  Map<String, String> toRecordJson() => {'name': name, 'price': price};
}

/// A scanned receipt, awaiting confirmation. `total` becomes the expense;
/// `items` become this user's price history once confirmed.
class ReceiptCandidate {
  const ReceiptCandidate({this.merchant, this.total, this.date, this.items = const [], this.reasons = const []});
  factory ReceiptCandidate.fromJson(Map<String, dynamic> j) => ReceiptCandidate(
        merchant: j['merchant'] as String?,
        total: j['total'] as String?,
        date: j['date'] as String?,
        items: [
          for (final i in (j['items'] as List? ?? const []))
            ReceiptLine.fromJson(Map<String, dynamic>.from(i as Map)),
        ],
        reasons: [for (final r in (j['reasons'] as List? ?? const [])) r.toString()],
      );
  final String? merchant;
  final String? total;
  final String? date;
  final List<ReceiptLine> items;
  final List<String> reasons;
}

class TransactionCaptureRepository {
  TransactionCaptureRepository(this._dio);
  final Dio _dio;

  /// Read a receipt's OCR text into a candidate, or null when it isn't a
  /// receipt we can act on.
  Future<ReceiptCandidate?> parseReceipt(String text) async {
    try {
      final res = await _dio.post<dynamic>('/transactions/parse-receipt', data: {'text': text});
      final cand = (res.data as Map)['candidate'];
      return cand == null ? null : ReceiptCandidate.fromJson(Map<String, dynamic>.from(cand as Map));
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

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

  /// Store confirmed receipt items as this user's price history. Called only on
  /// confirm — a parse alone never records anything.
  Future<int> recordItems({
    required List<Map<String, String>> items,
    required String currency,
    DateTime? observedOn,
    String? merchant,
  }) async {
    try {
      final res = await _dio.post<dynamic>('/transactions/record-items', data: {
        'items': items,
        'currency': currency,
        if (observedOn != null)
          'observed_on': '${observedOn.year.toString().padLeft(4, '0')}-'
              '${observedOn.month.toString().padLeft(2, '0')}-${observedOn.day.toString().padLeft(2, '0')}',
        if (merchant != null && merchant.isNotEmpty) 'merchant': merchant,
      });
      return (res.data as Map)['stored'] as int? ?? 0;
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final transactionCaptureRepositoryProvider = Provider<TransactionCaptureRepository>(
    (ref) => TransactionCaptureRepository(ref.watch(dioProvider)));
