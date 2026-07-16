import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../cache/offline_cache.dart';
import 'future_me_models.dart';

class FutureMeRepository {
  FutureMeRepository(this._dio, this._cache);
  final Dio _dio;
  final OfflineCache _cache;

  Future<FutureMeView> getFutureMe() async =>
      FutureMeView.fromJson(await _cache.fetchJson(_dio, '/advisor/future-me'));
}

final futureMeRepositoryProvider = Provider<FutureMeRepository>(
    (ref) => FutureMeRepository(ref.watch(dioProvider), ref.watch(offlineCacheProvider)));

final futureMeProvider =
    FutureProvider.autoDispose<FutureMeView>((ref) => ref.watch(futureMeRepositoryProvider).getFutureMe());
