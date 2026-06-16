import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Abstraction so tests can swap a fake (no platform channel) for the secure
/// implementation.
abstract class TokenStore {
  Future<String?> readAccess();
  Future<String?> readRefresh();
  Future<void> write({required String access, required String refresh});
  Future<void> clear();
}

class SecureTokenStore implements TokenStore {
  SecureTokenStore([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage();

  static const _accessKey = 'access_token';
  static const _refreshKey = 'refresh_token';
  final FlutterSecureStorage _storage;

  @override
  Future<String?> readAccess() => _storage.read(key: _accessKey);

  @override
  Future<String?> readRefresh() => _storage.read(key: _refreshKey);

  @override
  Future<void> write({required String access, required String refresh}) async {
    await _storage.write(key: _accessKey, value: access);
    await _storage.write(key: _refreshKey, value: refresh);
  }

  @override
  Future<void> clear() async {
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }
}

final tokenStoreProvider = Provider<TokenStore>((ref) => SecureTokenStore());
