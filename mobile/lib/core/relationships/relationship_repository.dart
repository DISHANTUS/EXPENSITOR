import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../cache/offline_cache.dart';
import 'relationship_models.dart';

class RelationshipRepository {
  RelationshipRepository(this._dio, this._cache);
  final Dio _dio;
  final OfflineCache _cache;

  Future<List<RelationshipSummary>> list() async {
    final json = await _cache.fetchJson(_dio, '/relationships');
    final people = (json['people'] as List?) ?? const [];
    return people.whereType<Map>().map((e) => RelationshipSummary.fromJson(e.cast<String, dynamic>())).toList();
  }

  Future<RelationshipDetail> detail(String name) async => RelationshipDetail.fromJson(
      await _cache.fetchJson(_dio, '/relationships/${Uri.encodeComponent(name)}'));
}

final relationshipRepositoryProvider = Provider<RelationshipRepository>(
    (ref) => RelationshipRepository(ref.watch(dioProvider), ref.watch(offlineCacheProvider)));

final relationshipsProvider =
    FutureProvider.autoDispose<List<RelationshipSummary>>((ref) => ref.watch(relationshipRepositoryProvider).list());

final relationshipDetailProvider =
    FutureProvider.autoDispose.family<RelationshipDetail, String>((ref, name) => ref.watch(relationshipRepositoryProvider).detail(name));
