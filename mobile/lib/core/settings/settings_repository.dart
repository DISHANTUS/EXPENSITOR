import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';

/// The subset of GET /users/me/settings the app needs. Base currency drives
/// money entry (no converter in Sprint 3A — amounts are entered in base).
class UserSettings {
  const UserSettings({required this.baseCurrency, this.aiTone, this.timezone});

  factory UserSettings.fromJson(Map<String, dynamic> j) => UserSettings(
        baseCurrency: (j['base_currency'] ?? 'INR').toString(),
        aiTone: j['preferred_ai_tone']?.toString(),
        timezone: j['timezone']?.toString(),
      );

  final String baseCurrency;
  final String? aiTone;
  final String? timezone;
}

class SettingsRepository {
  SettingsRepository(this._dio);
  final Dio _dio;

  Future<UserSettings> get() async {
    try {
      final res = await _dio.get<dynamic>('/users/me/settings');
      return UserSettings.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final settingsRepositoryProvider =
    Provider<SettingsRepository>((ref) => SettingsRepository(ref.watch(dioProvider)));

/// Cached for the life of the session shell; disposed on logout so a different
/// user never inherits the previous base currency.
final userSettingsProvider =
    FutureProvider.autoDispose<UserSettings>((ref) => ref.watch(settingsRepositoryProvider).get());
