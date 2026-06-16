import 'package:expensitor_mobile/core/auth/auth_state.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('resolveRedirect', () {
    test('unknown stays on splash, else routes to splash', () {
      expect(resolveRedirect(status: AuthStatus.unknown, location: '/splash'), isNull);
      expect(resolveRedirect(status: AuthStatus.unknown, location: '/home'), '/splash');
    });

    test('unauthenticated routes to login (and stays there)', () {
      expect(resolveRedirect(status: AuthStatus.unauthenticated, location: '/home'), '/login');
      expect(resolveRedirect(status: AuthStatus.unauthenticated, location: '/login'), isNull);
    });

    test('authenticated leaves splash/login for home, stays elsewhere', () {
      expect(resolveRedirect(status: AuthStatus.authenticated, location: '/splash'), '/home');
      expect(resolveRedirect(status: AuthStatus.authenticated, location: '/login'), '/home');
      expect(resolveRedirect(status: AuthStatus.authenticated, location: '/home'), isNull);
    });
  });
}
