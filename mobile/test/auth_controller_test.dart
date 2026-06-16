import 'package:expensitor_mobile/core/api/api_exception.dart';
import 'package:expensitor_mobile/core/auth/auth_controller.dart';
import 'package:expensitor_mobile/core/auth/auth_repository.dart';
import 'package:expensitor_mobile/core/auth/auth_state.dart';
import 'package:expensitor_mobile/core/auth/models.dart';
import 'package:expensitor_mobile/core/auth/token_store.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'support/fakes.dart';

ProviderContainer _container(MockAuthRepository repo, FakeTokenStore store) {
  final c = ProviderContainer(overrides: [
    tokenStoreProvider.overrideWithValue(store),
    authRepositoryProvider.overrideWithValue(repo),
  ]);
  addTearDown(c.dispose);
  return c;
}

void main() {
  const user = AppUser(id: '1', email: 'a@b.com');

  test('login success -> authenticated', () async {
    final repo = MockAuthRepository();
    when(() => repo.login('a@b.com', 'password1')).thenAnswer((_) async => user);
    final c = _container(repo, FakeTokenStore());

    await c.read(authControllerProvider.notifier).login('a@b.com', 'password1');

    final state = c.read(authControllerProvider);
    expect(state.status, AuthStatus.authenticated);
    expect(state.user?.email, 'a@b.com');
    expect(state.busy, isFalse);
  });

  test('login failure -> unauthenticated with error message', () async {
    final repo = MockAuthRepository();
    when(() => repo.login(any(), any())).thenThrow(const UnauthorizedError('Wrong email or password.'));
    final c = _container(repo, FakeTokenStore());

    await c.read(authControllerProvider.notifier).login('a@b.com', 'password1');

    final state = c.read(authControllerProvider);
    expect(state.status, AuthStatus.unauthenticated);
    expect(state.error, 'Wrong email or password.');
  });

  test('bootstrap with no token -> unauthenticated (no me call)', () async {
    final repo = MockAuthRepository();
    final c = _container(repo, FakeTokenStore());

    await c.read(authControllerProvider.notifier).bootstrap();

    expect(c.read(authControllerProvider).status, AuthStatus.unauthenticated);
    verifyNever(() => repo.me());
  });

  test('bootstrap with valid token -> authenticated', () async {
    final repo = MockAuthRepository();
    when(() => repo.me()).thenAnswer((_) async => user);
    final c = _container(repo, FakeTokenStore(access: 'tok', refresh: 'r'));

    await c.read(authControllerProvider.notifier).bootstrap();

    expect(c.read(authControllerProvider).status, AuthStatus.authenticated);
  });

  test('onSessionExpired -> unauthenticated', () {
    final repo = MockAuthRepository();
    final c = _container(repo, FakeTokenStore());
    c.read(authControllerProvider.notifier).onSessionExpired();
    expect(c.read(authControllerProvider).status, AuthStatus.unauthenticated);
  });

  test('logout clears and unauthenticates', () async {
    final repo = MockAuthRepository();
    when(() => repo.logout()).thenAnswer((_) async {});
    final store = FakeTokenStore(access: 'tok', refresh: 'r');
    final c = _container(repo, store);

    await c.read(authControllerProvider.notifier).logout();

    expect(c.read(authControllerProvider).status, AuthStatus.unauthenticated);
    verify(() => repo.logout()).called(1);
  });
}
