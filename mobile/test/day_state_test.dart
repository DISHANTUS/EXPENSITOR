import 'package:expensitor_mobile/core/home/day_state.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

const _channel = MethodChannel('plugins.it_nomads.com/flutter_secure_storage');

void _mockSecureStorage({String? seeded}) {
  final store = <String, String>{if (seeded != null) 'home_last_full_open_date': seeded};
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(_channel, (call) async {
    final args = (call.arguments as Map).cast<String, dynamic>();
    switch (call.method) {
      case 'write':
        store[args['key'] as String] = args['value'] as String;
        return null;
      case 'read':
        return store[args['key'] as String];
      default:
        return null;
    }
  });
}

String _todayKey() {
  final now = DateTime.now();
  final y = now.year.toString().padLeft(4, '0');
  final m = now.month.toString().padLeft(2, '0');
  final d = now.day.toString().padLeft(2, '0');
  return '$y-$m-$d';
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('first open ever (no stored date) shows the full calendar view', () async {
    _mockSecureStorage();
    final controller = HomeDayStateController(const FlutterSecureStorage());
    await Future<void>.delayed(Duration.zero); // let _init()'s await settle
    expect(controller.state, HomeViewMode.full);
  });

  test('a second open the same day shows the compact view', () async {
    _mockSecureStorage(seeded: _todayKey());
    final controller = HomeDayStateController(const FlutterSecureStorage());
    await Future<void>.delayed(Duration.zero);
    expect(controller.state, HomeViewMode.compact);
  });

  test('an open on a new day (stale stored date) shows the full view again', () async {
    _mockSecureStorage(seeded: '2000-01-01');
    final controller = HomeDayStateController(const FlutterSecureStorage());
    await Future<void>.delayed(Duration.zero);
    expect(controller.state, HomeViewMode.full);
  });

  test('forceFull() flips to full without needing storage to change', () async {
    _mockSecureStorage(seeded: _todayKey());
    final controller = HomeDayStateController(const FlutterSecureStorage());
    await Future<void>.delayed(Duration.zero);
    expect(controller.state, HomeViewMode.compact);

    controller.forceFull();
    expect(controller.state, HomeViewMode.full);
  });
}
