import 'dart:convert';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/services.dart' show AssetManifest, rootBundle;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import 'facts_models.dart';

/// Serves fun facts **offline-first**: the backend (the full, updatable set) is
/// preferred when reachable, and a small bundled starter pack guarantees the
/// companion never runs out of facts with no network. Parsing mirrors the backend
/// exactly — only `N. <fact>` lines survive, so a number/heading never reaches the
/// user.
class FactsRepository {
  FactsRepository(this._dio);
  final Dio _dio;

  // A fact line is "<number>. <text>"; everything else (banners, "--- X ---"
  // dividers, "END OF …" footers, blanks) is ignored.
  static final RegExp _factRe = RegExp(r'^\s*\d+\.\s+(.+?)\s*$');

  static const _emoji = {
    'money': '💰', 'study': '🎓', 'productivity': '🧠', 'world': '🌍', 'japan': '🇯🇵',
    'technology': '💻', 'gaming': '🎮', 'food': '🍜', 'animal': '🦊', 'animals': '🦊',
    'anime': '🎌', 'movie': '🎬', 'movies': '🎬', 'vehicle': '🚗', 'vehicles': '🚗',
    'weapons': '⚔️', 'beauty-fashion': '💄', 'love-and-romance': '❤️',
  };
  static const _dropTokens = {'facts', 'fact', '1000', 'truly', 'unique'};
  static const _smallWords = {'and', 'of', 'the', 'a', 'an', 'in', 'on', 'to', 'for'};

  static List<String> parseFacts(String raw) {
    final out = <String>[];
    for (final line in const LineSplitter().convert(raw)) {
      final m = _factRe.firstMatch(line);
      if (m != null) {
        final f = m.group(1)!.trim();
        if (f.isNotEmpty) out.add(f);
      }
    }
    return out;
  }

  static String _slug(String stem) {
    final tokens = stem.toLowerCase().split(RegExp(r'[^a-z0-9]+'))
        .where((t) => t.isNotEmpty && !_dropTokens.contains(t));
    final s = tokens.join('-');
    return s.isEmpty ? 'facts' : s;
  }

  static String _label(String slug) {
    final words = slug.split('-');
    return [
      for (var i = 0; i < words.length; i++)
        (_smallWords.contains(words[i]) && i > 0)
            ? words[i]
            : (words[i].isEmpty ? words[i] : '${words[i][0].toUpperCase()}${words[i].substring(1)}'),
    ].join(' ');
  }

  static String emojiFor(String slug) => _emoji[slug] ?? '💡';

  // --- Bundled assets (offline source) ---
  Map<String, ({String label, List<String> facts})>? _bundled;

  Future<Map<String, ({String label, List<String> facts})>> _loadBundled() async {
    if (_bundled != null) return _bundled!;
    final packs = <String, ({String label, List<String> facts})>{};
    try {
      final manifest = await AssetManifest.loadFromAssetBundle(rootBundle);
      final paths = manifest.listAssets().where((k) => k.startsWith('assets/facts/') && k.endsWith('.txt'));
      for (final path in paths) {
        final stem = path.split('/').last.replaceAll('.txt', '');
        final facts = parseFacts(await rootBundle.loadString(path));
        if (facts.isEmpty) continue;
        final slug = _slug(stem);
        final existing = packs[slug];
        packs[slug] = existing == null
            ? (label: _label(slug), facts: facts)
            : (label: existing.label, facts: [...existing.facts, ...facts]);
      }
    } catch (_) {/* no bundled facts → empty */}
    _bundled = packs;
    return packs;
  }

  Set<String> _enabled(Iterable<String> all, Set<String> disabled) {
    final e = all.where((k) => !disabled.contains(k)).toSet();
    return e.isEmpty ? all.toSet() : e;   // disabling everything → fall back to all
  }

  // --- Categories ---
  List<FactCategory>? _catCache;

  Future<List<FactCategory>> categories() async {
    if (_catCache != null) return _catCache!;
    try {
      final res = await _dio.get<dynamic>('/facts/categories');
      final list = (res.data as List).map((e) => FactCategory.fromJson((e as Map).cast<String, dynamic>())).toList();
      if (list.isNotEmpty) return _catCache = list;
    } catch (_) {/* offline → bundled */}
    final bundled = await _loadBundled();
    return _catCache = [
      for (final e in bundled.entries)
        FactCategory(key: e.key, label: e.value.label, emoji: emojiFor(e.key), count: e.value.facts.length),
    ];
  }

  String? _enabledQuery(List<FactCategory> cats, Set<String> disabled) {
    if (disabled.isEmpty) return null;   // all on → let the backend use everything
    final keys = _enabled(cats.map((c) => c.key), disabled);
    if (keys.length >= cats.length) return null;
    return keys.join(',');
  }

  Future<FactItem?> randomFact({Set<String> disabled = const {}}) async {
    final cats = await categories();
    try {
      final q = _enabledQuery(cats, disabled);
      final res = await _dio.get<dynamic>('/facts/random',
          queryParameters: {if (q != null) 'categories': q});
      return FactItem.fromJson((res.data as Map).cast<String, dynamic>());
    } catch (_) {
      return _bundledPick(disabled, (n) => Random().nextInt(n));
    }
  }

  Future<FactItem?> dailyFact(DateTime day, {Set<String> disabled = const {}}) async {
    final cats = await categories();
    final iso = '${day.year.toString().padLeft(4, '0')}-'
        '${day.month.toString().padLeft(2, '0')}-${day.day.toString().padLeft(2, '0')}';
    try {
      final q = _enabledQuery(cats, disabled);
      final res = await _dio.get<dynamic>('/facts/daily',
          queryParameters: {'date': iso, if (q != null) 'categories': q});
      return FactItem.fromJson((res.data as Map).cast<String, dynamic>());
    } catch (_) {
      // Deterministic offline pick — stable for the day.
      final seed = iso.codeUnits.fold<int>(7, (a, c) => (a * 31 + c) & 0x7fffffff);
      return _bundledPick(disabled, (n) => seed % n);
    }
  }

  Future<FactItem?> _bundledPick(Set<String> disabled, int Function(int n) index) async {
    final bundled = await _loadBundled();
    if (bundled.isEmpty) return null;
    final enabled = _enabled(bundled.keys, disabled);
    final pool = <({String text, String slug, String label})>[];
    for (final slug in enabled) {
      final p = bundled[slug]!;
      pool.addAll(p.facts.map((t) => (text: t, slug: slug, label: p.label)));
    }
    if (pool.isEmpty) return null;
    final pick = pool[index(pool.length) % pool.length];
    return FactItem(text: pick.text, category: pick.slug, categoryLabel: pick.label, emoji: emojiFor(pick.slug));
  }
}

final factsRepositoryProvider =
    Provider<FactsRepository>((ref) => FactsRepository(ref.watch(dioProvider)));

final factCategoriesProvider =
    FutureProvider<List<FactCategory>>((ref) => ref.watch(factsRepositoryProvider).categories());
