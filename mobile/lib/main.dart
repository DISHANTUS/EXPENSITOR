import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'core/theme/theme_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await applySavedTheme();             // restore the chosen theme pack before first paint
  await applySavedMotionIntensity();   // restore the ambient-motion preference
  runApp(const ProviderScope(child: ExpensitorApp()));
}
