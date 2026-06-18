import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import 'chat_models.dart';

class AdvisorChatRepository {
  AdvisorChatRepository(this._dio);
  final Dio _dio;

  Future<ChatTurn> send(String message, ChatContext? session) async {
    try {
      final res = await _dio.post<dynamic>('/advisor/chat', data: {
        'message': message,
        if (session != null) 'session': session.toJson(),
      });
      return ChatTurn.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<Explanation> explain(String ref, ChatContext? session) async {
    try {
      final res = await _dio.post<dynamic>('/advisor/explain', data: {
        'ref': ref,
        if (session != null) 'session': session.toJson(),
      });
      return Explanation.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Re-run a forecast with a set of applied lever refs (tapped chips).
  Future<Forecast> forecast(List<String> levers, ChatContext? session, {String? question}) async {
    try {
      final res = await _dio.post<dynamic>('/advisor/forecast', data: {
        if (question != null) 'question': question,
        'levers': levers,
        if (session != null) 'session': session.toJson(),
      });
      return Forecast.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Answer a learning-loop check-in (records a Phase-E Outcome server-side).
  Future<FollowUpAck> answerFollowUp(String adviceId, String answer, {String? detail}) async {
    try {
      final res = await _dio.post<dynamic>('/advisor/follow-ups/$adviceId/answer', data: {
        'answer': answer,
        if (detail != null) 'detail': detail,
      });
      return FollowUpAck.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Due "what happened?" check-ins (for a dedicated surface, optional).
  Future<List<FollowUpQuestion>> followUps() async {
    try {
      final res = await _dio.get<dynamic>('/advisor/follow-ups');
      return (res.data as List)
          .whereType<Map>()
          .map((e) => FollowUpQuestion.fromJson(e.cast<String, dynamic>()))
          .toList();
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Answer a month-end / win reflection (becomes a positive lesson).
  Future<String> answerReflection(String trigger, String value) async {
    try {
      final res = await _dio.post<dynamic>('/advisor/reflection/answer',
          data: {'trigger': trigger, 'answer': value});
      return (res.data as Map)['acknowledged']?.toString() ?? 'Thanks for reflecting.';
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Forget a lesson (reversible).
  Future<void> forgetLesson(String lessonId) async {
    try {
      await _dio.post<dynamic>('/advisor/lessons/$lessonId/forget');
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final advisorChatRepositoryProvider =
    Provider<AdvisorChatRepository>((ref) => AdvisorChatRepository(ref.watch(dioProvider)));
