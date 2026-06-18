import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import 'relationship_models.dart';

class RelationshipRepository {
  RelationshipRepository(this._dio);
  final Dio _dio;

  Future<List<RelationshipSummary>> list() async {
    try {
      final res = await _dio.get<dynamic>('/relationships');
      final people = ((res.data as Map)['people'] as List?) ?? const [];
      return people.whereType<Map>().map((e) => RelationshipSummary.fromJson(e.cast<String, dynamic>())).toList();
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<RelationshipDetail> detail(String name) async {
    try {
      final res = await _dio.get<dynamic>('/relationships/${Uri.encodeComponent(name)}');
      return RelationshipDetail.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final relationshipRepositoryProvider =
    Provider<RelationshipRepository>((ref) => RelationshipRepository(ref.watch(dioProvider)));

final relationshipsProvider =
    FutureProvider.autoDispose<List<RelationshipSummary>>((ref) => ref.watch(relationshipRepositoryProvider).list());

final relationshipDetailProvider =
    FutureProvider.autoDispose.family<RelationshipDetail, String>((ref, name) => ref.watch(relationshipRepositoryProvider).detail(name));
