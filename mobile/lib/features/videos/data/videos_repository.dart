import 'package:dio/dio.dart';

import '../../../core/api/api_client.dart';
import '../../../core/result.dart';
import '../domain/models.dart';

class VideosRepository {
  VideosRepository(this._api);

  final ApiClient _api;

  Future<Result<List<Video>>> list() => _api.call((dio) async {
        final r = await dio.get<List<dynamic>>('/videos');
        return [for (final v in r.data!) Video.fromJson(v as Map<String, dynamic>)];
      });

  Future<Result<Video>> get(String id) => _api.call((dio) async {
        final r = await dio.get<Map<String, dynamic>>('/videos/$id');
        return Video.fromJson(r.data!);
      });

  Future<Result<Video>> upload(
    String filePath,
    String fileName, {
    void Function(double progress)? onProgress,
    CancelToken? cancelToken,
  }) =>
      _api.call((dio) async {
        final form = FormData.fromMap({
          'file': await MultipartFile.fromFile(filePath, filename: fileName),
        });
        final r = await dio.post<Map<String, dynamic>>(
          '/videos',
          data: form,
          cancelToken: cancelToken,
          // upload de vídeo grande em rede móvel pode demorar bastante
          options: Options(sendTimeout: const Duration(hours: 1)),
          onSendProgress: (sent, total) {
            if (total > 0) onProgress?.call(sent / total);
          },
        );
        return Video.fromJson(r.data!);
      });

  Future<Result<void>> delete(String id) => _api.call((dio) => dio.delete<void>('/videos/$id'));

  Future<Result<Short>> patchShort(String videoId, int shortId, ShortPatch patch) =>
      _api.call((dio) async {
        final r = await dio.patch<Map<String, dynamic>>(
          '/videos/$videoId/shorts/$shortId',
          data: patch.toJson(),
        );
        return Short.fromJson(r.data!);
      });

  Future<Result<void>> download(
    String videoId,
    int shortId,
    String savePath, {
    void Function(double progress)? onProgress,
  }) =>
      _api.call((dio) => dio.download(
            '/videos/$videoId/shorts/$shortId/video',
            savePath,
            onReceiveProgress: (received, total) {
              if (total > 0) onProgress?.call(received / total);
            },
          ));

  /// A versão vai na query para o player/cache não reaproveitar um render antigo.
  Uri videoUri(String videoId, Short short) =>
      _api.uri('/videos/$videoId/shorts/${short.id}/video', {'v': '${short.render.version}'});

  Uri thumbUri(String videoId, Short short) =>
      _api.uri('/videos/$videoId/shorts/${short.id}/thumb', {'v': '${short.render.version}'});

  Map<String, String> get authHeaders => _api.authHeaders;
}
