import 'package:dio/dio.dart';

/// Typed application errors mapped from Dio failures so the UI can render
/// consistent messages without inspecting raw HTTP.
sealed class AppError implements Exception {
  const AppError(this.message);
  final String message;

  @override
  String toString() => '$runtimeType: $message';
}

class NetworkError extends AppError {
  const NetworkError([super.message = 'No connection. Check your network and try again.']);
}

class UnauthorizedError extends AppError {
  const UnauthorizedError([super.message = 'Your session has expired. Please log in again.']);
}

class ValidationError extends AppError {
  const ValidationError(super.message, [this.fields = const {}]);
  final Map<String, String> fields;
}

class ServerError extends AppError {
  const ServerError([super.message = 'Something went wrong on our side. Please try again.']);
}

class UnknownError extends AppError {
  const UnknownError([super.message = 'Unexpected error. Please try again.']);
}

AppError mapDioError(DioException e) {
  switch (e.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.receiveTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.connectionError:
      return const NetworkError();
    case DioExceptionType.badResponse:
      return _fromResponse(e.response);
    case DioExceptionType.cancel:
      return const UnknownError('Request cancelled.');
    case DioExceptionType.badCertificate:
    case DioExceptionType.unknown:
      return e.error is AppError ? e.error as AppError : const NetworkError();
  }
}

AppError _fromResponse(Response<dynamic>? response) {
  final status = response?.statusCode ?? 0;
  if (status == 401 || status == 403) return const UnauthorizedError();
  if (status == 422) return _validation(response?.data);
  if (status >= 500) return const ServerError();
  // 4xx with a string detail
  final detail = _detailString(response?.data);
  return ValidationError(detail ?? 'Request could not be completed.');
}

/// FastAPI returns `detail` either as a string (our HTTPException usage) or a
/// list of `{loc, msg, type}` (Pydantic validation). Handle both.
ValidationError _validation(dynamic data) {
  if (data is Map && data['detail'] is String) {
    return ValidationError(data['detail'] as String);
  }
  if (data is Map && data['detail'] is List) {
    final fields = <String, String>{};
    for (final item in data['detail'] as List) {
      if (item is Map) {
        final loc = (item['loc'] as List?)?.cast<dynamic>() ?? const [];
        final field = loc.isNotEmpty ? loc.last.toString() : 'value';
        fields[field] = (item['msg'] ?? 'Invalid value').toString();
      }
    }
    final msg = fields.isEmpty ? 'Please check your input.' : fields.values.first;
    return ValidationError(msg, fields);
  }
  return const ValidationError('Please check your input.');
}

String? _detailString(dynamic data) {
  if (data is Map && data['detail'] is String) return data['detail'] as String;
  return null;
}
