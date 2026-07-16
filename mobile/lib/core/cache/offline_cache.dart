import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../api/api_exception.dart';

/// A GET that transparently falls back to the last successful response when
/// the live call fails with a network-class error — so a returning,
/// already-authenticated user sees their last-known data instead of a blank
/// or error screen. [AuthController.bootstrap] already keeps that user
/// signed in through a network blip; this is the other half, for the data
/// screens themselves. Never used for writes — a failed write always throws.
class OfflineCache {
  OfflineCache([FlutterSecureStorage? storage]) : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;
  static const _prefix = 'cache_';

  /// True while at least one screen is currently showing cached (not live)
  /// data. Flips back the moment any [fetchJson] call succeeds live.
  final ValueNotifier<bool> isOffline = ValueNotifier<bool>(false);

  Future<void> _put(String key, Map<String, dynamic> json) =>
      _storage.write(key: '$_prefix$key', value: jsonEncode(json));

  Future<Map<String, dynamic>?> _read(String key) async {
    final raw = await _storage.read(key: '$_prefix$key');
    if (raw == null) return null;
    try {
      return (jsonDecode(raw) as Map).cast<String, dynamic>();
    } catch (_) {
      return null; // corrupt/old-shape entry — treat as a miss, not a crash
    }
  }

  String _cacheKey(String path, Map<String, dynamic>? query) =>
      query == null ? path : '$path?${query.entries.map((e) => '${e.key}=${e.value}').join('&')}';

  Future<Map<String, dynamic>> fetchJson(Dio dio, String path, {Map<String, dynamic>? query}) async {
    final key = _cacheKey(path, query);
    try {
      final res = await dio.get<dynamic>(path, queryParameters: query);
      final json = (res.data as Map).cast<String, dynamic>();
      unawaited(_put(key, json));
      isOffline.value = false;
      return json;
    } on DioException catch (e) {
      final error = mapDioError(e);
      if (error is NetworkError) {
        final cached = await _read(key);
        if (cached != null) {
          isOffline.value = true;
          return cached;
        }
      }
      throw error;
    }
  }
}

final offlineCacheProvider = Provider<OfflineCache>((ref) => OfflineCache());
