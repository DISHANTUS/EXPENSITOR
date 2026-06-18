/// A single fun fact + which category it came from.
class FactItem {
  const FactItem({required this.text, required this.category, required this.categoryLabel, required this.emoji});

  final String text;
  final String category;       // slug, e.g. "money"
  final String categoryLabel;  // display, e.g. "Money"
  final String emoji;

  factory FactItem.fromJson(Map<String, dynamic> j) => FactItem(
        text: (j['text'] ?? '') as String,
        category: (j['category'] ?? '') as String,
        categoryLabel: (j['category_label'] ?? '') as String,
        emoji: (j['emoji'] ?? '💡') as String,
      );
}

/// A fact category and how many facts it holds.
class FactCategory {
  const FactCategory({required this.key, required this.label, required this.emoji, required this.count});

  final String key;
  final String label;
  final String emoji;
  final int count;

  factory FactCategory.fromJson(Map<String, dynamic> j) => FactCategory(
        key: (j['key'] ?? '') as String,
        label: (j['label'] ?? '') as String,
        emoji: (j['emoji'] ?? '💡') as String,
        count: (j['count'] ?? 0) as int,
      );
}
