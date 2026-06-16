import 'models.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

class AuthState {
  const AuthState({
    this.status = AuthStatus.unknown,
    this.user,
    this.busy = false,
    this.error,
  });

  final AuthStatus status;
  final AppUser? user;
  final bool busy;
  final String? error;

  AuthState copyWith({
    AuthStatus? status,
    AppUser? user,
    bool? busy,
    String? error,
    bool clearError = false,
    bool clearUser = false,
  }) =>
      AuthState(
        status: status ?? this.status,
        user: clearUser ? null : (user ?? this.user),
        busy: busy ?? this.busy,
        error: clearError ? null : (error ?? this.error),
      );
}

/// Pure routing decision (unit-tested). Sprint 2 will extend this for the
/// onboarding gate.
String? resolveRedirect({required AuthStatus status, required String location}) {
  switch (status) {
    case AuthStatus.unknown:
      return location == '/splash' ? null : '/splash';
    case AuthStatus.unauthenticated:
      return location == '/login' ? null : '/login';
    case AuthStatus.authenticated:
      return (location == '/login' || location == '/splash') ? '/home' : null;
  }
}
