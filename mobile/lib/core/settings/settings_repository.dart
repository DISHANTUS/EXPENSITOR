import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';

/// The subset of GET /users/me/settings the app needs. Base currency drives
/// money entry/display (the user's "preferred currency").
class UserSettings {
  const UserSettings({
    required this.baseCurrency,
    this.aiTone,
    this.timezone,
    this.companionStyle = 'balanced',
    this.voiceLength = 'normal',
    this.selectedVoice,
    this.voiceLocale,
    this.companionName,
    this.displayName,
    this.notificationPreferences = const {},
  });

  factory UserSettings.fromJson(Map<String, dynamic> j) => UserSettings(
        baseCurrency: (j['base_currency'] ?? 'INR').toString(),
        aiTone: j['preferred_ai_tone']?.toString(),
        timezone: j['timezone']?.toString(),
        companionStyle: (j['companion_style'] ?? 'balanced').toString(),
        voiceLength: (j['voice_length'] ?? 'normal').toString(),
        selectedVoice: j['selected_voice']?.toString(),
        voiceLocale: j['voice_locale']?.toString(),
        companionName: j['companion_name']?.toString(),
        displayName: j['display_name']?.toString(),
        notificationPreferences: ((j['notification_preferences'] as Map?) ?? const {})
            .map((k, v) => MapEntry(k.toString(), v == true)),
      );

  final String baseCurrency;
  final String? aiTone;
  final String? timezone;
  final String companionStyle;
  final String voiceLength;
  final String? selectedVoice;
  final String? voiceLocale;
  final String? companionName;
  final String? displayName;
  final Map<String, bool> notificationPreferences;
}

/// AI's interpretation of a free-text reason (original is preserved by caller).
class ReasonInterpretation {
  const ReasonInterpretation({
    required this.original,
    required this.label,
    required this.tags,
    required this.confidence,
    required this.needsMore,
  });

  factory ReasonInterpretation.fromJson(Map<String, dynamic> j) => ReasonInterpretation(
        original: (j['original'] ?? '').toString(),
        label: (j['label'] ?? '').toString(),
        tags: ((j['tags'] as List?) ?? const []).map((e) => e.toString()).toList(),
        confidence: (j['confidence'] as num?)?.toDouble() ?? 0,
        needsMore: j['needs_more'] == true,
      );

  final String original;
  final String label;
  final List<String> tags;
  final double confidence;
  final bool needsMore;

  /// What to persist in ai_metadata so the user's words are never lost.
  Map<String, dynamic> toMetadata() =>
      {'why_original': original, 'why_label': label, 'confidence': confidence, 'tags': tags};
}

class SettingsRepository {
  SettingsRepository(this._dio);
  final Dio _dio;

  Future<UserSettings> get() => _get('/users/me/settings', UserSettings.fromJson);

  Future<List<String>> currencies() async {
    try {
      final res = await _dio.get<dynamic>('/currencies');
      final list = (res.data as List?) ?? const [];
      return list.whereType<Map>().map((e) => (e['code'] ?? '').toString()).where((c) => c.isNotEmpty).toList();
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<UserSettings> setBaseCurrency(String code) async {
    try {
      final res = await _dio.patch<dynamic>('/users/me/settings', data: {'base_currency': code});
      return UserSettings.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<UserSettings> setCompanionStyle(String style) async {
    try {
      final res = await _dio.patch<dynamic>('/users/me/settings', data: {'companion_style': style});
      return UserSettings.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<UserSettings> setNotificationPreferences(Map<String, bool> prefs) async {
    try {
      final res = await _dio.patch<dynamic>('/users/me/settings', data: {'notification_preferences': prefs});
      return UserSettings.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<UserSettings> setVoiceLength(String length) async {
    try {
      final res = await _dio.patch<dynamic>('/users/me/settings', data: {'voice_length': length});
      return UserSettings.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Choose the device TTS voice Advary speaks with (Voice Studio). Pass null to
  /// clear and fall back to the system default.
  Future<UserSettings> setSelectedVoice(String? name, String? locale) async {
    try {
      final res = await _dio.patch<dynamic>('/users/me/settings',
          data: {'selected_voice': name ?? '', 'voice_locale': locale});
      return UserSettings.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Set (or clear with '') the companion's name (Sprint 6c).
  Future<UserSettings> setCompanionName(String name) async {
    try {
      final res = await _dio.patch<dynamic>('/users/me/settings', data: {'companion_name': name});
      return UserSettings.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// What the user wants to be called (asked in onboarding; shown instead of email).
  Future<UserSettings> setDisplayName(String name) async {
    try {
      final res = await _dio.patch<dynamic>('/users/me/settings', data: {'display_name': name});
      return UserSettings.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Reset / clean-slate (pre-Sprint-8): mode = soft | full | demo.
  Future<void> reset(String mode) async {
    try {
      await _dio.post<dynamic>('/reset', data: {'mode': mode});
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Developer-only: seed this month with one of each event type (to test the
  /// Living Calendar animations + orb reactions). Returns how many were added.
  Future<int> seedCalendarPreview() async {
    try {
      final res = await _dio.post<dynamic>('/dev/calendar-preview');
      return ((res.data as Map)['created'] as num?)?.toInt() ?? 0;
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// When exchange rates were last updated, their source, and whether they're stale.
  Future<RatesStatus> ratesStatus() async {
    try {
      final res = await _dio.get<dynamic>('/currency/rates-status');
      return RatesStatus.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Pull the latest public exchange rates (only fetches if stale unless [force]).
  Future<RatesStatus> refreshRates({bool force = false}) async {
    try {
      final res = await _dio.post<dynamic>('/currency/refresh',
          queryParameters: {'force': force});
      return RatesStatus.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Returns the converted amount as a string.
  Future<String> convert(String amount, String from, String to) async {
    try {
      final res = await _dio.post<dynamic>('/currency/convert',
          data: {'amount': amount, 'from_currency': from.toUpperCase(), 'to_currency': to.toUpperCase()});
      final data = (res.data as Map).cast<String, dynamic>();
      return (data['converted_amount'] ?? data['amount'] ?? '0').toString();
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<ReasonInterpretation> interpretReason(String text) async {
    try {
      final res = await _dio.post<dynamic>('/reason/interpret', data: {'text': text});
      return ReasonInterpretation.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<T> _get<T>(String path, T Function(Map<String, dynamic>) parse) async {
    try {
      final res = await _dio.get<dynamic>(path);
      return parse((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final settingsRepositoryProvider =
    Provider<SettingsRepository>((ref) => SettingsRepository(ref.watch(dioProvider)));

final userSettingsProvider =
    FutureProvider.autoDispose<UserSettings>((ref) => ref.watch(settingsRepositoryProvider).get());

final currenciesProvider =
    FutureProvider.autoDispose<List<String>>((ref) => ref.watch(settingsRepositoryProvider).currencies());

/// Freshness of the exchange-rate table (date + source + stale flag).
class RatesStatus {
  const RatesStatus({this.rateDate, this.source, this.stale = true});
  factory RatesStatus.fromJson(Map<String, dynamic> j) => RatesStatus(
        rateDate: j['rate_date']?.toString(),
        source: j['source']?.toString(),
        stale: j['stale'] == true,
      );
  final String? rateDate;
  final String? source;
  final bool stale;
}

final ratesStatusProvider =
    FutureProvider.autoDispose<RatesStatus>((ref) => ref.watch(settingsRepositoryProvider).ratesStatus());
