import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// The user's privacy choice for keeping exchange rates updated. Stored on-device
/// (not synced) — refreshing only downloads public exchange-rate data, no personal
/// data leaves the app.
enum RatesConsent { unset, allow, never }

class RatesPrefs {
  RatesPrefs(this._storage);
  final FlutterSecureStorage _storage;
  static const _key = 'rates_auto_update';

  Future<RatesConsent> get() async {
    switch (await _storage.read(key: _key)) {
      case 'allow':
        return RatesConsent.allow;
      case 'never':
        return RatesConsent.never;
      default:
        return RatesConsent.unset;
    }
  }

  Future<void> set(RatesConsent c) => _storage.write(key: _key, value: c.name);
}

final ratesPrefsProvider = Provider<RatesPrefs>((_) => RatesPrefs(const FlutterSecureStorage()));
