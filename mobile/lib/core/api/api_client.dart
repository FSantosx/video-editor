import 'package:dio/dio.dart';

import '../result.dart';

/// Cliente HTTP da API de shorts. Adiciona a API key e converte erros em [Failure].
class ApiClient {
  ApiClient({required this.baseUrl, required this.apiKey, Dio? dio})
      : dio = dio ??
            Dio(BaseOptions(
              baseUrl: baseUrl,
              connectTimeout: const Duration(seconds: 15),
              receiveTimeout: const Duration(seconds: 60),
              headers: {if (apiKey.isNotEmpty) 'X-API-Key': apiKey},
            ));

  final String baseUrl;
  final String apiKey;
  final Dio dio;

  /// Headers para quem acessa a API fora do dio (ex.: video_player).
  Map<String, String> get authHeaders => {if (apiKey.isNotEmpty) 'X-API-Key': apiKey};

  Uri uri(String path, [Map<String, String>? query]) =>
      Uri.parse(baseUrl).resolve(path).replace(queryParameters: query);

  Future<Result<T>> call<T>(Future<T> Function(Dio dio) request) async {
    try {
      return Ok(await request(dio));
    } on DioException catch (e) {
      return Err(mapDioError(e));
    } on FormatException catch (e) {
      return Err(Failure(FailureKind.unknown, e.message));
    }
  }
}

Failure mapDioError(DioException e) {
  final response = e.response;
  if (response == null) {
    return Failure(FailureKind.network, e.message);
  }
  final data = response.data;
  final detail = data is Map ? data['detail']?.toString() : null;
  return switch (response.statusCode) {
    401 => Failure(FailureKind.unauthorized, detail),
    404 => Failure(FailureKind.notFound, detail),
    413 => Failure(FailureKind.tooLarge, detail),
    415 || 422 => Failure(FailureKind.invalid, detail),
    final code? when code >= 500 => Failure(FailureKind.server, detail),
    _ => Failure(FailureKind.unknown, detail),
  };
}
