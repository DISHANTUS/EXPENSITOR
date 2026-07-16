import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';

/// What Advary understood from one free-text planning sentence. Every field is
/// nullable on purpose — this is a head start for the flow, never a verdict.
/// Whatever comes back null simply gets asked for, exactly as it always was.
class PlanningIntent {
  const PlanningIntent({
    required this.kind,
    this.item,
    this.amount,
    this.targetDate,
    this.missing = const [],
    this.source = 'rules',
  });

  factory PlanningIntent.fromJson(Map<String, dynamic> j) => PlanningIntent(
        kind: (j['kind'] ?? 'other').toString(),
        item: (j['item'] as String?)?.trim().isEmpty ?? true ? null : (j['item'] as String).trim(),
        amount: j['amount'] == null ? null : double.tryParse(j['amount'].toString()),
        targetDate: j['target_date'] == null ? null : DateTime.tryParse(j['target_date'].toString()),
        missing: [for (final m in (j['missing'] as List? ?? const [])) m.toString()],
        source: (j['source'] ?? 'rules').toString(),
      );

  final String kind; // buy | subscription | save | other
  final String? item;
  final double? amount;
  final DateTime? targetDate;
  final List<String> missing;
  final String source; // rules | model — which layer worked it out

  /// True when we understood nothing useful and should just let the user pick.
  bool get isEmpty => kind == 'other' && item == null && amount == null;
}

class PlanningRepository {
  PlanningRepository(this._dio);
  final Dio _dio;

  Future<PlanningIntent> interpret(String text) async {
    try {
      final res = await _dio.post<dynamic>('/planning/interpret', data: {'text': text});
      return PlanningIntent.fromJson(Map<String, dynamic>.from(res.data as Map));
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final planningRepositoryProvider =
    Provider<PlanningRepository>((ref) => PlanningRepository(ref.watch(dioProvider)));
