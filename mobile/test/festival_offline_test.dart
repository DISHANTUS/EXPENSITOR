import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:expensitor_mobile/core/cache/offline_cache.dart';
import 'package:expensitor_mobile/features/budget_setup/festival_repository.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

/// Festivals on a phone with no internet.
///
/// This is the one thing worth proving here: the dates are fixed months ahead,
/// so a cached answer is exactly as true as a live one. Showing a blank card to
/// someone on a train is a self-inflicted wound.
///
/// Mirrors offline_cache_test.dart's harness — FlutterSecureStorage talks to a
/// real plugin that doesn't exist in a unit test, so its channel is backed by an
/// in-memory map.
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
    final bytes = utf8.encode(jsonEncode(next));
    return ResponseBody.fromBytes(bytes, 200,
        headers: {Headers.contentTypeHeader: [Headers.jsonContentType]});
  }
}

Dio _dioWith(List<Object> script) => Dio()..httpClientAdapter = _ScriptedAdapter(script);

Map<String, dynamic> _payload(String name) => {
      'ready': true,
      'regions': ['IN'],
      'currency': 'INR',
      'calendar_until': '2028-12-25',
      'upcoming': [
        {
          'name': name,
          'date': '2026-11-08',
          'days_away': 114,
          'approximate': false,
          'line': '$name is in 114 days.',
        }
      ],
    };

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(_mockSecureStorage);

  test('a live answer is served and kept on the phone', () async {
    final cache = OfflineCache();
    final repo = FestivalRepository(_dioWith([_payload('Diwali')]), cache);

    final live = await repo.upcoming();
    expect(live.upcoming.single.name, 'Diwali');
    expect(live.regions, ['IN']);
    expect(cache.isOffline.value, isFalse);
  });

  test('with no internet, the festival still shows from cache', () async {
    final cache = OfflineCache();

    // Warm it while online...
    await FestivalRepository(_dioWith([_payload('Diwali')]), cache).upcoming();

    // ...then the phone loses the network entirely.
    final offlineRepo = FestivalRepository(_dioWith([DioExceptionType.connectionError]), cache);
    final result = await offlineRepo.upcoming();

    expect(result.upcoming.single.name, 'Diwali', reason: 'a fixed future date is as true offline as online');
    expect(result.upcoming.single.line, 'Diwali is in 114 days.');
    expect(cache.isOffline.value, isTrue, reason: 'and the app knows it is showing cached data');
  });

  test('going back online replaces the cached copy', () async {
    final cache = OfflineCache();
    await FestivalRepository(_dioWith([_payload('Diwali')]), cache).upcoming();

    // A newer answer from the server wins — the cache must never pin an old one.
    final fresh = await FestivalRepository(_dioWith([_payload('Guru Nanak Jayanti')]), cache).upcoming();
    expect(fresh.upcoming.single.name, 'Guru Nanak Jayanti');
    expect(cache.isOffline.value, isFalse);
  });

  test('offline with nothing cached fails rather than inventing a festival', () async {
    // A blank card is honest; a made-up festival is not. The card renders
    // nothing on error, which is the right end state.
    final repo = FestivalRepository(_dioWith([DioExceptionType.connectionError]), OfflineCache());
    await expectLater(repo.upcoming(), throwsA(anything));
  });
}
