import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import 'voice_plan.dart';

/// The companion's spoken reply to a transcript (mirrors backend VoiceAskOut).
class VoiceReply {
  const VoiceReply({
    required this.type,
    required this.speech,
    required this.voice,
    this.navigate,
    this.session,
    this.awaiting,
    this.commandText,
    this.requestId,
    this.action,
    this.requiresConfirmation = false,
  });

  final String type;                  // turn type | clarification | preview | result | …
  final String speech;                // concise spoken line
  final VoicePlan voice;              // paced delivery (5b)
  final String? navigate;             // screen to open after speaking
  final Map<String, dynamic>? session; // echoed conversation memory
  // Multi-turn write flow (5c-B):
  final String? awaiting;             // slot the next utterance fills
  final String? commandText;          // original command to resend
  final String? requestId;            // echo on the confirm/execute turn
  final String? action;               // intent executed/previewed (-> reaction ack)
  final bool requiresConfirmation;    // speak summary, then listen yes/no

  bool get wantsFollowUp => type == 'clarify' || type == 'follow_up';
  bool get isWriteFollowUp => awaiting != null || requiresConfirmation;

  factory VoiceReply.fromJson(Map<String, dynamic> j) => VoiceReply(
        type: (j['type'] ?? 'answer').toString(),
        speech: (j['speech'] ?? '').toString(),
        voice: j['voice'] is Map
            ? VoicePlan.fromJson((j['voice'] as Map).cast<String, dynamic>())
            : const VoicePlan(),
        navigate: j['navigate']?.toString(),
        session: j['session'] is Map ? (j['session'] as Map).cast<String, dynamic>() : null,
        awaiting: j['awaiting']?.toString(),
        commandText: j['command_text']?.toString(),
        requestId: j['request_id']?.toString(),
        action: j['action']?.toString(),
        requiresConfirmation: j['requires_confirmation'] == true,
      );
}

class VoiceRepository {
  VoiceRepository(this._dio);
  final Dio _dio;

  Future<VoiceReply> ask(
    String text, {
    Map<String, dynamic>? session,
    String? commandText,
    Map<String, String>? answers,
    bool confirm = false,
    String? requestId,
  }) async {
    try {
      final res = await _dio.post<dynamic>('/voice/ask', data: {
        'text': text,
        if (session != null) 'session': session,
        if (commandText != null) 'command_text': commandText,
        if (answers != null && answers.isNotEmpty) 'answers': answers,
        if (confirm) 'confirm': true,
        if (requestId != null) 'request_id': requestId,
      });
      return VoiceReply.fromJson((res.data as Map).cast<String, dynamic>());
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

final voiceRepositoryProvider = Provider<VoiceRepository>((ref) => VoiceRepository(ref.watch(dioProvider)));
