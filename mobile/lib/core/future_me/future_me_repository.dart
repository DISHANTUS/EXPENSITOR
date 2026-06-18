import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import 'future_me_models.dart';

class FutureMeRepository {
  FutureMeRepository(this._dio);
  final Dio _dio;

  Future<FutureMeView> getFutureMe() async {
    try {
      final res = await _dio.get<dynamic>('/advisor/future-me');
      return FutureMeView.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final futureMeRepositoryProvider =
    Provider<FutureMeRepository>((ref) => FutureMeRepository(ref.watch(dioProvider)));

final futureMeProvider =
    FutureProvider.autoDispose<FutureMeView>((ref) => ref.watch(futureMeRepositoryProvider).getFutureMe());
