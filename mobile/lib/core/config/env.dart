/// Build-time configuration. Override with:
///   flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000/api/v1
///
/// Default targets the Android emulator's host loopback (10.0.2.2) on the
/// docker-compose API port. iOS simulator can use http://localhost:8000/api/v1.
class Env {
  const Env._();

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );
}
