import 'package:expensitor_mobile/app.dart';
import 'package:expensitor_mobile/core/auth/token_store.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fakes.dart';

void main() {
  testWidgets('cold start with no token lands on the Login screen', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [tokenStoreProvider.overrideWithValue(FakeTokenStore())],
        child: const ExpensitorApp(),
      ),
    );
    // Let the Splash bootstrap microtask resolve, then the router redirect.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text('Log in'), findsOneWidget);
  });
}
