import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

/// Schedules a single local notification for the next time the user said
/// they're usually free, when a spending-shift follow-up is waiting for an
/// explanation — asking at a good time instead of interrupting mid-task.
///
/// Purely local: this app has no push/backend-scheduler infrastructure (and
/// doesn't need one for this) — the client notices a due follow-up next time
/// it's opened and schedules one local alert for the appropriate slot.
/// Defensive by design: any plugin/platform failure (e.g. an unsupported
/// desktop target, permissions denied) is swallowed, never crashes the app —
/// the in-app follow-up card is always the reliable fallback either way.
class LocalNotificationService {
  LocalNotificationService([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;
  final _plugin = FlutterLocalNotificationsPlugin();
  static const _scheduledPrefix = 'notif_scheduled_advice_';
  bool _initialized = false;

  static const _clockTimes = {
    'morning': (9, 0),
    'afternoon': (14, 0),
    'evening': (18, 0),
    'night': (21, 0),
  };

  Future<bool> _ensureInitialized() async {
    if (_initialized) return true;
    try {
      tzdata.initializeTimeZones();
      const android = AndroidInitializationSettings('@mipmap/ic_launcher');
      const ios = DarwinInitializationSettings();
      const linux = LinuxInitializationSettings(defaultActionName: 'Open');
      await _plugin.initialize(
        const InitializationSettings(android: android, iOS: ios, macOS: ios, linux: linux),
      );
      // Android 13+ requires the runtime notification permission explicitly;
      // a decline here just means the scheduled call below silently no-ops —
      // the in-app follow-up card still works regardless.
      await _plugin
          .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
          ?.requestNotificationsPermission();
      await _plugin
          .resolvePlatformSpecificImplementation<IOSFlutterLocalNotificationsPlugin>()
          ?.requestPermissions(alert: true, badge: true, sound: true);
      _initialized = true;
      return true;
    } catch (_) {
      return false; // unsupported platform or init failure — caller no-ops
    }
  }

  tz.TZDateTime _nextSlot(String weekdaySlot, String weekendSlot) {
    final now = tz.TZDateTime.now(tz.local);
    for (var addDays = 0; addDays < 8; addDays++) {
      final day = now.add(Duration(days: addDays));
      final isWeekend = day.weekday == DateTime.saturday || day.weekday == DateTime.sunday;
      final slot = isWeekend ? weekendSlot : weekdaySlot;
      final (h, m) = _clockTimes[slot] ?? _clockTimes['evening']!;
      final candidate = tz.TZDateTime(tz.local, day.year, day.month, day.day, h, m);
      if (candidate.isAfter(now)) return candidate;
    }
    return now.add(const Duration(hours: 3)); // unreachable in practice
  }

  /// Schedules (once per advice id — checked against local storage, so a
  /// repeat call from a later Home load is a safe no-op) a nudge for the
  /// user's next stated free-time slot.
  Future<void> scheduleExplainReminder({
    required String adviceId,
    required String title,
    required String body,
    required String weekdaySlot,
    required String weekendSlot,
  }) async {
    try {
      final key = '$_scheduledPrefix$adviceId';
      if (await _storage.read(key: key) != null) return;
      if (!await _ensureInitialized()) return;

      final when = _nextSlot(weekdaySlot, weekendSlot);
      await _plugin.zonedSchedule(
        adviceId.hashCode,
        title,
        body,
        when,
        const NotificationDetails(
          android: AndroidNotificationDetails(
            'spending_shift', 'Spending changes',
            channelDescription: "A nudge to explain a spending change, timed for when you're free",
          ),
          iOS: DarwinNotificationDetails(),
          macOS: DarwinNotificationDetails(),
        ),
        androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
        uiLocalNotificationDateInterpretation: UILocalNotificationDateInterpretation.absoluteTime,
        payload: adviceId,
      );
      await _storage.write(key: key, value: 'scheduled');
    } catch (e) {
      if (kDebugMode) debugPrint('LocalNotificationService: schedule failed ($e)');
      // Never crash the app over a notification — the in-app follow-up card
      // (Home's compact view) is always there regardless.
    }
  }

  /// Clears the "already scheduled" flag once a follow-up is answered, so a
  /// *future*, unrelated spending_shift item isn't blocked by a stale key
  /// (ids are per-advice-row, so this is mostly defensive cleanup).
  Future<void> cancelForAdvice(String adviceId) async {
    try {
      await _plugin.cancel(adviceId.hashCode);
      await _storage.delete(key: '$_scheduledPrefix$adviceId');
    } catch (_) {
      // best-effort
    }
  }
}

final localNotificationServiceProvider = Provider<LocalNotificationService>((ref) => LocalNotificationService());
