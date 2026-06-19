import 'dart:async';

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
  ///
  /// A free-tier cold start (~50s) or a network blip must NEVER sign the user out
  /// — only a genuine auth failure (401) does. So we retry transient errors, and
  /// if the server simply stays unreachable we keep the session (the token is
  /// valid) and fill the profile in the background once it responds.
  Future<void> bootstrap() async {
    final token = await _store.readAccess();
    if (token == null) {
      state = const AuthState(status: AuthStatus.unauthenticated);
      return;
    }
    for (var attempt = 0; attempt < 3; attempt++) {
      try {
        final user = await _repo.me();
        state = AuthState(status: AuthStatus.authenticated, user: user);
        return;
      } on UnauthorizedError {
        await _store.clear();
        state = const AuthState(status: AuthStatus.unauthenticated);
        return;
      } on AppError {
        if (attempt < 2) await Future<void>.delayed(Duration(seconds: 2 * (attempt + 1)));
      }
    }
    // Token exists but the server stayed unreachable — stay signed in.
    state = const AuthState(status: AuthStatus.authenticated);
    unawaited(_fillProfileWhenReachable());
  }

  /// After an optimistic sign-in (server was unreachable), keep trying to load
  /// the profile so user-dependent features light up once the backend wakes.
  Future<void> _fillProfileWhenReachable() async {
    for (var i = 0; i < 5 && state.status == AuthStatus.authenticated && state.user == null; i++) {
      await Future<void>.delayed(Duration(seconds: 6 * (i + 1)));
      try {
        final user = await _repo.me();
        if (state.status == AuthStatus.authenticated) {
          state = AuthState(status: AuthStatus.authenticated, user: user);
        }
        return;
      } on UnauthorizedError {
        return; // the interceptor handles genuine session loss
      } on AppError {
        // keep waiting for the server
      }
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

  /// Remember (locally) that the first-launch tour has been seen, so the gate
  /// doesn't re-trigger this session. The server is updated separately.
  void markTourSeen() {
    final u = state.user;
    if (u != null && !u.hasSeenTour) {
      state = state.copyWith(user: u.copyWith(hasSeenTour: true));
    }
  }

  /// Invoked by the API interceptor when refresh fails mid-session.
  void onSessionExpired() {
    state = const AuthState(status: AuthStatus.unauthenticated, error: 'Your session expired. Please log in again.');
  }
}

final authControllerProvider = NotifierProvider<AuthController, AuthState>(AuthController.new);
