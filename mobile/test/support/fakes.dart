import 'package:expensitor_mobile/core/auth/auth_repository.dart';
import 'package:expensitor_mobile/core/auth/token_store.dart';
import 'package:mocktail/mocktail.dart';

class FakeTokenStore implements TokenStore {
  FakeTokenStore({this.access, this.refresh});
  String? access;
  String? refresh;

  @override
  Future<String?> readAccess() async => access;

  @override
  Future<String?> readRefresh() async => refresh;

  @override
  Future<void> write({required String access, required String refresh}) async {
    this.access = access;
    this.refresh = refresh;
  }

  @override
  Future<void> clear() async {
    access = null;
    refresh = null;
  }
}

class MockAuthRepository extends Mock implements AuthRepository {}
