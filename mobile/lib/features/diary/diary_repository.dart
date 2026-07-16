import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';

/// One of Advary's follow-ups and what the user said back.
class DiaryDetail {
  const DiaryDetail({required this.question, required this.answer});
  factory DiaryDetail.fromJson(Map<String, dynamic> j) => DiaryDetail(
        question: (j['question'] ?? '').toString(),
        answer: (j['answer'] ?? '').toString(),
      );
  final String question;
  final String answer;
}

class DiaryEntry {
  const DiaryEntry({
    required this.id,
    required this.entryDate,
    required this.text,
    this.details = const [],
    this.closed = false,
    this.pendingQuestion,
  });

  factory DiaryEntry.fromJson(Map<String, dynamic> j) => DiaryEntry(
        id: (j['id'] ?? '').toString(),
        entryDate: DateTime.tryParse((j['entry_date'] ?? '').toString()) ?? DateTime.now(),
        text: (j['text'] ?? '').toString(),
        details: [
          for (final d in (j['details'] as List? ?? const []))
            DiaryDetail.fromJson(Map<String, dynamic>.from(d as Map)),
        ],
        closed: j['closed'] == true,
        pendingQuestion: j['pending_question'] as String?,
      );

  final String id;
  final DateTime entryDate;
  final String text;
  final List<DiaryDetail> details;
  final bool closed;

  /// A question the model worked out after the fact, while the user was away.
  /// Null for almost every entry.
  final String? pendingQuestion;
}

/// An entry plus the next thing Advary would like to ask. A null question is
/// normal — it means there's nothing worth asking, not that something failed.
class DiaryReply {
  const DiaryReply({required this.entry, this.question});
  factory DiaryReply.fromJson(Map<String, dynamic> j) => DiaryReply(
        entry: DiaryEntry.fromJson(Map<String, dynamic>.from(j['entry'] as Map)),
        question: j['question'] as String?,
      );
  final DiaryEntry entry;
  final String? question;
}

class PatternObservation {
  const PatternObservation({required this.kind, required this.word, required this.text});
  factory PatternObservation.fromJson(Map<String, dynamic> j) => PatternObservation(
        kind: (j['kind'] ?? '').toString(),
        word: (j['word'] ?? '').toString(),
        text: (j['text'] ?? '').toString(),
      );
  final String kind;
  final String word;
  final String text;
}

class DiaryPatterns {
  const DiaryPatterns({
    required this.ready,
    required this.entries,
    this.days = 0,
    this.needed = 0,
    this.observations = const [],
    this.askWord,
    this.askQuestion,
  });

  factory DiaryPatterns.fromJson(Map<String, dynamic> j) {
    final ask = j['ask'] as Map?;
    return DiaryPatterns(
      ready: j['ready'] == true,
      entries: (j['entries'] as num?)?.toInt() ?? 0,
      days: (j['days'] as num?)?.toInt() ?? 0,
      needed: (j['needed'] as num?)?.toInt() ?? 0,
      observations: [
        for (final o in (j['observations'] as List? ?? const []))
          PatternObservation.fromJson(Map<String, dynamic>.from(o as Map)),
      ],
      askWord: ask?['word']?.toString(),
      askQuestion: ask?['question']?.toString(),
    );
  }

  /// False until there's enough written to say anything. Under the threshold
  /// this stays empty on purpose rather than guessing.
  final bool ready;
  final int entries;
  final int days;
  final int needed;
  final List<PatternObservation> observations;
  final String? askWord;
  final String? askQuestion;
}

class DiaryRepository {
  DiaryRepository(this._dio);
  final Dio _dio;

  Future<DiaryReply> write(String text) async {
    try {
      final res = await _dio.post<dynamic>('/diary', data: {'text': text});
      return DiaryReply.fromJson(Map<String, dynamic>.from(res.data as Map));
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<DiaryReply> answer(String entryId, {required String question, required String answer}) async {
    try {
      final res = await _dio.post<dynamic>(
        '/diary/$entryId/answer',
        data: {'question': question, 'answer': answer},
      );
      return DiaryReply.fromJson(Map<String, dynamic>.from(res.data as Map));
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<void> close(String entryId) async {
    try {
      await _dio.post<dynamic>('/diary/$entryId/close');
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<void> delete(String entryId) async {
    try {
      await _dio.delete<dynamic>('/diary/$entryId');
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<List<DiaryEntry>> list() async {
    try {
      final res = await _dio.get<dynamic>('/diary', queryParameters: {'limit': 50});
      return [
        for (final e in (res.data as List))
          DiaryEntry.fromJson(Map<String, dynamic>.from(e as Map)),
      ];
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<DiaryPatterns> patterns() async {
    try {
      final res = await _dio.get<dynamic>('/diary/patterns');
      return DiaryPatterns.fromJson(Map<String, dynamic>.from(res.data as Map));
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final diaryRepositoryProvider = Provider<DiaryRepository>((ref) => DiaryRepository(ref.watch(dioProvider)));

final diaryEntriesProvider =
    FutureProvider.autoDispose<List<DiaryEntry>>((ref) => ref.watch(diaryRepositoryProvider).list());

final diaryPatternsProvider =
    FutureProvider.autoDispose<DiaryPatterns>((ref) => ref.watch(diaryRepositoryProvider).patterns());
