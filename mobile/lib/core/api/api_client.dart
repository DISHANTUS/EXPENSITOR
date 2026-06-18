import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_controller.dart';
import '../auth/token_store.dart';
import '../config/env.dart';
import 'auth_interceptor.dart';

BaseOptions _baseOptions() => BaseOptions(
      baseUrl: Env.apiBaseUrl,
      // Generous connect timeout so the first request survives a free-tier host
      // cold start (~50s wake). Lower this if you move to an always-on instance.
      connectTimeout: const Duration(seconds: 60),
      receiveTimeout: const Duration(seconds: 30),
      contentType: 'application/json',
      // Let our interceptor/mapper decide; don't throw inside Dio for <500.
      validateStatus: (s) => s != null && s < 400,
    );

/// A plain Dio (no auth interceptor) used for refresh + retry. Exposed so the
/// interceptor cannot recurse through itself.
final refreshDioProvider = Provider<Dio>((ref) => Dio(_baseOptions()));

/// The app-wide authenticated client.
final dioProvider = Provider<Dio>((ref) {
  final store = ref.watch(tokenStoreProvider);
  final dio = Dio(_baseOptions());
  dio.interceptors.add(
    AuthInterceptor(
      store: store,
      refreshDio: ref.watch(refreshDioProvider),
      // Lazy read at runtime only — no build-time provider cycle.
      onSessionExpired: () => ref.read(authControllerProvider.notifier).onSessionExpired(),
    ),
  );
  return dio;
});
