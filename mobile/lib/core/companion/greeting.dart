/// Time-of-day greeting for the companion's opening line. Sprint 3 ships this
/// basic version; Sprint 4 layers personalization (habits, goals) and priority
/// items (urgent/important/friendly) on top via the advisor engine.
String timeGreeting([DateTime? now]) {
  final hour = (now ?? DateTime.now()).hour;
  if (hour < 12) return 'Good morning — let’s make today count.';
  if (hour < 17) return 'Good afternoon — hope you’ve eaten well.';
  if (hour < 21) return 'Good evening — let’s review today.';
  return 'Good evening — be sure to get some rest tonight.';
}
