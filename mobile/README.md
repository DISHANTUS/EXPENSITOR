# Expensitor Mobile (Flutter)

Mobile client for the Expensitor advisor backend. **Consumes the existing API
without modification.** Productization Phase 1.

## Status — Sprint 1 (scaffold + auth)
Implemented: Flutter scaffold, Riverpod, Dio API layer (auth bearer + refresh-on-401),
secure token storage, routing with auth redirect guards, Splash, Login/Register, empty Home.
**Goal of this sprint:** a user can log in / register and reach the (empty) Home screen.

## Prerequisites
- Flutter SDK (3.19+ / Dart 3.3+).
- The backend running (docker compose) — see repo root.

## First-time setup
This repo commits only `lib/`, `test/`, and `pubspec.yaml`. Generate the platform
folders locally (does not touch `lib/`):

```bash
cd mobile
flutter create . --platforms=android,ios --org com.expensitor
flutter pub get
```

> Android cleartext HTTP: the dev backend is plain HTTP. For a real device/emulator,
> allow cleartext to your API host in `android/app/src/main/AndroidManifest.xml`
> (`android:usesCleartextTraffic="true"` for debug) — not needed for `flutter test`.

## Run
```bash
# Android emulator reaches the host API at 10.0.2.2 (default).
flutter run
# Or point at a specific host:
flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000/api/v1
```

## Validate (this sprint's tests)
```bash
cd mobile
flutter pub get
flutter analyze
flutter test
```
Sprint-1 tests: `api_exception` mapping, `resolveRedirect` guard logic,
`AuthInterceptor.shouldAttemptRefresh`, `AuthController` (login/register/bootstrap/
logout/session-expiry) with fakes, and a Login smoke widget test.

## Layout
```
lib/
  main.dart, app.dart
  core/
    config/env.dart
    api/ (api_client, auth_interceptor, api_exception)
    auth/ (token_store, models, auth_repository, auth_controller, auth_state)
    router/app_router.dart
    theme/app_theme.dart
  features/ (splash, auth, home)
test/ (+ test/support/fakes.dart)
```

## Notes
- No codegen in Sprint 1 (hand-written DTOs) so the project builds with just `flutter pub get`.
- freezed/json_serializable can be adopted later if model volume grows.
- Backend gap noted in the plan: no `GET /categories` endpoint — expense capture in
  later sprints routes through the Assistant (server-side category resolution) or
  uncategorized.
