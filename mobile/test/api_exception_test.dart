import 'package:dio/dio.dart';
import 'package:expensitor_mobile/core/api/api_exception.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final ro = RequestOptions(path: '/x');

  DioException dio(DioExceptionType type, {Response<dynamic>? response}) =>
      DioException(requestOptions: ro, type: type, response: response);

  test('timeouts and connection errors map to NetworkError', () {
    expect(mapDioError(dio(DioExceptionType.connectionTimeout)), isA<NetworkError>());
    expect(mapDioError(dio(DioExceptionType.receiveTimeout)), isA<NetworkError>());
    expect(mapDioError(dio(DioExceptionType.connectionError)), isA<NetworkError>());
  });

  test('401/403 map to UnauthorizedError', () {
    final r = Response<dynamic>(requestOptions: ro, statusCode: 401);
    expect(mapDioError(dio(DioExceptionType.badResponse, response: r)), isA<UnauthorizedError>());
  });

  test('422 with string detail maps to ValidationError message', () {
    final r = Response<dynamic>(requestOptions: ro, statusCode: 422, data: {'detail': 'invalid kind: x'});
    final err = mapDioError(dio(DioExceptionType.badResponse, response: r));
    expect(err, isA<ValidationError>());
    expect(err.message, 'invalid kind: x');
  });

  test('422 with field list maps to ValidationError fields', () {
    final r = Response<dynamic>(requestOptions: ro, statusCode: 422, data: {
      'detail': [
        {'loc': ['body', 'email'], 'msg': 'value is not a valid email', 'type': 'value_error'},
      ],
    });
    final err = mapDioError(dio(DioExceptionType.badResponse, response: r)) as ValidationError;
    expect(err.fields['email'], 'value is not a valid email');
  });

  test('5xx maps to ServerError', () {
    final r = Response<dynamic>(requestOptions: ro, statusCode: 500);
    expect(mapDioError(dio(DioExceptionType.badResponse, response: r)), isA<ServerError>());
  });
}
