import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:expensitor_mobile/core/api/api_exception.dart';
import 'package:expensitor_mobile/core/cache/offline_cache.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

/// [FlutterSecureStorage] talks to a real platform plugin, which doesn't
/// exist in a bare unit test — so back its method channel with a simple
/// in-memory map, fresh per test.
const _secureStorageChannel = MethodChannel('plugins.it_nomads.com/flutter_secure_storage');

void _mockSecureStorage() {
  final store = <String, String>{};
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(_secureStorageChannel, (call) async {
    final args = (call.arguments as Map).cast<String, dynamic>();
    switch (call.method) {
      case 'write':
        store[args['key'] as String] = args['value'] as String;
        return null;
      case 'read':
        return store[args['key'] as String];
      case 'delete':
        store.remove(args['key'] as String);
        return null;
      case 'readAll':
        return store;
      case 'deleteAll':
        store.clear();
        return null;
      case 'containsKey':
        return store.containsKey(args['key'] as String);
      default:
        return null;
    }
  });
}

/// A non-2xx scripted response — Dio itself turns this into a `badResponse`
/// DioException once the adapter hands it back (real HTTP-error behavior,
/// not a connection-level failure).
class _Status {
  _Status(this.code, this.body);
  final int code;
  final Map<String, dynamic> body;
}

/// Replays a scripted sequence of responses: a Map for a 200 JSON body, a
/// [_Status] for a non-2xx JSON body, or a [DioExceptionType] to simulate a
/// connection-level failure on the next call.
class _ScriptedAdapter implements HttpClientAdapter {
  _ScriptedAdapter(this._script);
  final List<Object> _script;
  var _i = 0;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
      RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    final next = _script[_i++];
    if (next is DioExceptionType) {
      throw DioException(requestOptions: options, type: next);
    }
    final status = next is _Status ? next.code : 200;
    final body = next is _Status ? next.body : next;
    final bytes = utf8.encode(jsonEncode(body));
    return ResponseBody.fromBytes(bytes, status,
        headers: {Headers.contentTypeHeader: [Headers.jsonContentType]});
  }
}

Dio _dioWith(List<Object> script) => Dio()..httpClientAdapter = _ScriptedAdapter(script);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(_mockSecureStorage);

  test('caches a live response, then serves it back on a later network failure', () async {
    final cache = OfflineCache(const FlutterSecureStorage());
    final dio = _dioWith([
      {'value': 'live-once'},
      DioExceptionType.connectionError,
    ]);

    final live = await cache.fetchJson(dio, '/offline-cache-test/reads-through');
    expect(live, {'value': 'live-once'});
    expect(cache.isOffline.value, isFalse);

    final fallback = await cache.fetchJson(dio, '/offline-cache-test/reads-through');
    expect(fallback, {'value': 'live-once'}, reason: 'should replay the last cached body');
    expect(cache.isOffline.value, isTrue);
  });

  test('rethrows NetworkError when nothing has ever been cached for that key', () async {
    final cache = OfflineCache(const FlutterSecureStorage());
    final dio = _dioWith([DioExceptionType.connectionError]);

    await expectLater(
      cache.fetchJson(dio, '/offline-cache-test/never-cached'),
      throwsA(isA<NetworkError>()),
    );
  });

  test('a fresh live call after a cache fallback clears isOffline again', () async {
    final cache = OfflineCache(const FlutterSecureStorage());
    final dio = _dioWith([
      {'value': 'a'},
      DioExceptionType.connectionError,
      {'value': 'b'},
    ]);

    await cache.fetchJson(dio, '/offline-cache-test/recovers');
    await cache.fetchJson(dio, '/offline-cache-test/recovers'); // falls back, isOffline -> true
    expect(cache.isOffline.value, isTrue);

    final recovered = await cache.fetchJson(dio, '/offline-cache-test/recovers');
    expect(recovered, {'value': 'b'});
    expect(cache.isOffline.value, isFalse);
  });

  test('a non-network error (e.g. expired session) is never masked by a stale cache', () async {
    final cache = OfflineCache(const FlutterSecureStorage());
    final dio = _dioWith([
      {'value': 'seen-once'},
      _Status(401, {'detail': 'Could not validate credentials'}),
    ]);

    final first = await cache.fetchJson(dio, '/offline-cache-test/unauthorized');
    expect(first, {'value': 'seen-once'});

    // A cache entry now exists for this key, but a 401 must still surface —
    // silently falling back here would hide a real session expiry.
    await expectLater(
      cache.fetchJson(dio, '/offline-cache-test/unauthorized'),
      throwsA(isA<UnauthorizedError>()),
    );
  });
}
