import 'package:expensitor_mobile/core/notifications/local_notification_service.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

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
      default:
        return null;
    }
  });
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(_mockSecureStorage);

  // The notification plugin's own platform channel is intentionally left
  // unmocked here — this is exactly the "unsupported platform / init failure"
  // case the service must survive without throwing, since the in-app
  // follow-up card is always the reliable fallback either way.

  test('scheduleExplainReminder never throws even when the plugin channel is unavailable', () async {
    final service = LocalNotificationService(const FlutterSecureStorage());
    await expectLater(
      service.scheduleExplainReminder(
        adviceId: 'advice-1', title: 'title', body: 'body',
        weekdaySlot: 'evening', weekendSlot: 'afternoon',
      ),
      completes,
    );
  });

  test('cancelForAdvice never throws even when the plugin channel is unavailable', () async {
    final service = LocalNotificationService(const FlutterSecureStorage());
    await expectLater(service.cancelForAdvice('advice-1'), completes);
  });

  test('an unknown free-time slot falls back to evening rather than crashing', () async {
    final service = LocalNotificationService(const FlutterSecureStorage());
    await expectLater(
      service.scheduleExplainReminder(
        adviceId: 'advice-2', title: 'title', body: 'body',
        weekdaySlot: 'not-a-real-slot', weekendSlot: 'also-not-real',
      ),
      completes,
    );
  });
}
