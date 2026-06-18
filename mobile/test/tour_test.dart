import 'package:dio/dio.dart';
import 'package:expensitor_mobile/core/onboarding/tour_controller.dart';
import 'package:expensitor_mobile/core/onboarding/tour_repository.dart';
import 'package:expensitor_mobile/core/router/app_router.dart';
import 'package:expensitor_mobile/core/voice/voice_service.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

class _FakeTts implements TtsEngine {
  final List<String> spoken = [];
  @override
  Future<void> configure() async {}
  @override
  Future<void> setStyle({required double rate, required double pitch, double volume = 1.0}) async {}
  @override
  Future<void> speak(String text) async => spoken.add(text);
  @override
  Future<void> stop() async {}
  @override
  set onComplete(void Function()? cb) {}
  @override
  set onCancel(void Function()? cb) {}
}

/// A TourRepository that returns canned steps and records completion, with no Dio.
class _FakeTourRepo extends TourRepository {
  _FakeTourRepo() : super(Dio());
  bool completed = false;

  @override
  Future<Tour> fetch() async => const Tour(companionName: 'Advary', steps: [
        TourStep(key: 'welcome', route: '/home', icon: '👋', title: 'Meet Advary',
            narration: 'hi', spokenText: 'hi'),
        TourStep(key: 'home', route: '/home', icon: '🗓️', title: 'Home',
            narration: 'calendar', spokenText: 'calendar'),
        TourStep(key: 'done', route: '/home', icon: '✨', title: 'Set',
            narration: 'bye', spokenText: 'bye'),
      ]);

  @override
  Future<void> markComplete() async => completed = true;
}

ProviderContainer _container(_FakeTourRepo repo) => ProviderContainer(overrides: [
      tourRepositoryProvider.overrideWithValue(repo),
      ttsEngineProvider.overrideWithValue(_FakeTts()),
      routerProvider.overrideWithValue(
        GoRouter(routes: [GoRoute(path: '/home', builder: (_, __) => const SizedBox.shrink())]),
      ),
    ]);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Tour parsing', () {
    test('Tour.fromJson reads companion name + ordered steps', () {
      final t = Tour.fromJson({
        'companion_name': 'Kai',
        'steps': [
          {'key': 'home', 'route': '/home', 'icon': '🗓️', 'title': 'Home',
           'narration': 'n', 'spoken_text': 's'},
        ],
      });
      expect(t.companionName, 'Kai');
      expect(t.steps.single.route, '/home');
      expect(t.steps.single.spokenText, 's');
    });

    test('TourStep falls back spoken_text → narration', () {
      final s = TourStep.fromJson({'key': 'x', 'route': '/home', 'narration': 'only'});
      expect(s.spokenText, 'only');
    });
  });

  group('TourState', () {
    test('current / isFirst / isLast track the index', () {
      const steps = [
        TourStep(key: 'a', route: '/home', icon: '', title: '', narration: '', spokenText: ''),
        TourStep(key: 'b', route: '/home', icon: '', title: '', narration: '', spokenText: ''),
      ];
      const s0 = TourState(active: true, steps: steps, index: 0);
      expect(s0.isFirst, isTrue);
      expect(s0.isLast, isFalse);
      expect(s0.current!.key, 'a');
      final s1 = s0.copyWith(index: 1);
      expect(s1.isLast, isTrue);
      expect(s1.current!.key, 'b');
    });
  });

  group('TourController', () {
    test('start activates and lands on the first step', () async {
      final repo = _FakeTourRepo();
      final c = _container(repo);
      addTearDown(c.dispose);

      await c.read(tourControllerProvider.notifier).start();
      final s = c.read(tourControllerProvider);
      expect(s.active, isTrue);
      expect(s.index, 0);
      expect(s.steps.length, 3);
      expect(s.companionName, 'Advary');
    });

    test('next/back walk the steps; finishing dismisses and stamps complete', () async {
      final repo = _FakeTourRepo();
      final c = _container(repo);
      addTearDown(c.dispose);
      final n = c.read(tourControllerProvider.notifier);

      await n.start();
      n.next();
      expect(c.read(tourControllerProvider).index, 1);
      n.back();
      expect(c.read(tourControllerProvider).index, 0);
      n.next();
      n.next();   // now on the last step
      expect(c.read(tourControllerProvider).isLast, isTrue);
      n.next();   // finish
      expect(c.read(tourControllerProvider).active, isFalse);
      expect(repo.completed, isTrue);
    });

    test('skip dismisses immediately and marks complete', () async {
      final repo = _FakeTourRepo();
      final c = _container(repo);
      addTearDown(c.dispose);
      final n = c.read(tourControllerProvider.notifier);

      await n.start();
      n.skip();
      expect(c.read(tourControllerProvider).active, isFalse);
      expect(repo.completed, isTrue);
    });
  });
}
