import 'package:dio/dio.dart';

import '../auth/token_store.dart';

/// Attaches the bearer token and transparently refreshes once on a 401.
///
/// Uses a SEPARATE [refreshDio] (no interceptor) for the refresh call + the
/// retry, so it can never recurse. Auth endpoints are never bearer-decorated
/// and never trigger a refresh.
class AuthInterceptor extends Interceptor {
  AuthInterceptor({
    required this.store,
    required this.refreshDio,
    required this.onSessionExpired,
  });

  final TokenStore store;
  final Dio refreshDio;
  final void Function() onSessionExpired;

  static const _retriedKey = 'expensitor_retried';

  static bool isAuthPath(String path) => path.contains('/auth/');

  /// Pure decision helper (unit-tested).
  static bool shouldAttemptRefresh({
    required int? statusCode,
    required String path,
    required bool alreadyRetried,
  }) =>
      statusCode == 401 && !isAuthPath(path) && !alreadyRetried;

  @override
  Future<void> onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    if (!isAuthPath(options.path)) {
      final token = await store.readAccess();
      if (token != null) options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(DioException err, ErrorInterceptorHandler handler) async {
    final retried = err.requestOptions.extra[_retriedKey] == true;
    if (!shouldAttemptRefresh(
      statusCode: err.response?.statusCode,
      path: err.requestOptions.path,
      alreadyRetried: retried,
    )) {
      return handler.next(err);
    }

    final outcome = await _tryRefresh();
    if (outcome != _RefreshOutcome.refreshed) {
      // Only a genuine rejection (bad/expired refresh token) ends the session.
      // A network blip / cold start keeps it — the request just fails this once.
      if (outcome == _RefreshOutcome.rejected) onSessionExpired();
      return handler.next(err);
    }

    try {
      final token = await store.readAccess();
      final options = err.requestOptions
        ..extra[_retriedKey] = true
        ..headers['Authorization'] = 'Bearer $token';
      final response = await refreshDio.fetch<dynamic>(options);
      return handler.resolve(response);
    } on DioException {
      return handler.next(err);
    }
  }

  Future<_RefreshOutcome> _tryRefresh() async {
    final refresh = await store.readRefresh();
    if (refresh == null) return _RefreshOutcome.rejected;
    try {
      final res = await refreshDio.post<dynamic>('/auth/refresh', data: {'refresh_token': refresh});
      final data = res.data as Map<String, dynamic>;
      await store.write(access: data['access_token'] as String, refresh: data['refresh_token'] as String);
      return _RefreshOutcome.refreshed;
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      if (code == 401 || code == 403) {
        await store.clear(); // the refresh token is genuinely invalid
        return _RefreshOutcome.rejected;
      }
      return _RefreshOutcome.networkError; // keep tokens; don't sign the user out
    }
  }
}

enum _RefreshOutcome { refreshed, rejected, networkError }
