import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import 'models.dart';
import 'token_store.dart';

class AuthRepository {
  AuthRepository(this._dio, this._store);

  final Dio _dio;
  final TokenStore _store;

  Future<AppUser> login(String email, String password) async {
    try {
      final res = await _dio.post<dynamic>('/auth/login', data: {'email': email, 'password': password});
      final tokens = TokenPair.fromJson(res.data as Map<String, dynamic>);
      await _store.write(access: tokens.accessToken, refresh: tokens.refreshToken);
      return me();
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<AppUser> register(String email, String password) async {
    try {
      await _dio.post<dynamic>('/auth/register', data: {'email': email, 'password': password});
    } on DioException catch (e) {
      throw mapDioError(e);
    }
    return login(email, password);
  }

  Future<AppUser> me() async {
    try {
      final res = await _dio.get<dynamic>('/users/me');
      return AppUser.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<void> logout() async {
    final refresh = await _store.readRefresh();
    try {
      await _dio.post<dynamic>('/auth/logout', data: {'refresh_token': refresh});
    } on DioException {
      // Logout is best-effort; always clear local tokens.
    } finally {
      await _store.clear();
    }
  }
}

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepository(ref.watch(dioProvider), ref.watch(tokenStoreProvider)),
);
