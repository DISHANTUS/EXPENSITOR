import 'package:expensitor_mobile/core/api/auth_interceptor.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('AuthInterceptor.shouldAttemptRefresh', () {
    test('401 on a non-auth path, not yet retried -> refresh', () {
      expect(AuthInterceptor.shouldAttemptRefresh(statusCode: 401, path: '/financial-health', alreadyRetried: false), isTrue);
    });

    test('401 on an auth path -> never refresh (no recursion)', () {
      expect(AuthInterceptor.shouldAttemptRefresh(statusCode: 401, path: '/auth/login', alreadyRetried: false), isFalse);
      expect(AuthInterceptor.shouldAttemptRefresh(statusCode: 401, path: '/auth/refresh', alreadyRetried: false), isFalse);
    });

    test('already retried -> do not loop', () {
      expect(AuthInterceptor.shouldAttemptRefresh(statusCode: 401, path: '/users/me', alreadyRetried: true), isFalse);
    });

    test('non-401 -> no refresh', () {
      expect(AuthInterceptor.shouldAttemptRefresh(statusCode: 500, path: '/users/me', alreadyRetried: false), isFalse);
      expect(AuthInterceptor.shouldAttemptRefresh(statusCode: 422, path: '/users/me', alreadyRetried: false), isFalse);
    });
  });
}
