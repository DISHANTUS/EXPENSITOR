/// Build-time configuration. Override with:
///   flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000/api/v1
///
/// Default targets the live Render backend so a plain build works on a
/// physical phone and on the laptop with no flags. For local backend dev,
/// override with --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
/// (Android emulator) or http://localhost:8000/api/v1 (iOS simulator/desktop).
class Env {
  const Env._();

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://expensitor-api.onrender.com/api/v1',
  );
}
