import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_exception.dart';
import 'auth_repository.dart';
import 'auth_state.dart';
import 'models.dart';
import 'token_store.dart';

class AuthController extends Notifier<AuthState> {
  @override
  AuthState build() => const AuthState();

  AuthRepository get _repo => ref.read(authRepositoryProvider);
  TokenStore get _store => ref.read(tokenStoreProvider);

  /// Called by Splash: validate any stored session.
  Future<void> bootstrap() async {
    final token = await _store.readAccess();
    if (token == null) {
      state = const AuthState(status: AuthStatus.unauthenticated);
      return;
    }
    try {
      final user = await _repo.me();
      state = AuthState(status: AuthStatus.authenticated, user: user);
    } on AppError {
      await _store.clear();
      state = const AuthState(status: AuthStatus.unauthenticated);
    }
  }

  Future<void> login(String email, String password) => _run(() => _repo.login(email, password));

  Future<void> register(String email, String password) => _run(() => _repo.register(email, password));

  Future<void> _run(Future<AppUser> Function() action) async {
    state = state.copyWith(busy: true, clearError: true);
    try {
      final user = await action();
      state = AuthState(status: AuthStatus.authenticated, user: user);
    } on AppError catch (e) {
      state = AuthState(status: AuthStatus.unauthenticated, error: e.message);
    } catch (_) {
      state = const AuthState(status: AuthStatus.unauthenticated, error: 'Unexpected error. Please try again.');
    }
  }

  Future<void> logout() async {
    await _repo.logout();
    state = const AuthState(status: AuthStatus.unauthenticated);
  }

  /// Invoked by the API interceptor when refresh fails mid-session.
  void onSessionExpired() {
    state = const AuthState(status: AuthStatus.unauthenticated, error: 'Your session expired. Please log in again.');
  }
}

final authControllerProvider = NotifierProvider<AuthController, AuthState>(AuthController.new);
