import '../../../core/api/api_client.dart';
import '../../../core/result.dart';
import '../domain/publish_models.dart';

class PublishRepository {
  PublishRepository(this._api);

  final ApiClient _api;

  Future<Result<PublishSettings>> settings() => _api.call((dio) async {
        final r = await dio.get<Map<String, dynamic>>('/publish/settings');
        return PublishSettings.fromJson(r.data!);
      });

  Future<Result<PublishSettings>> saveSlots(List<String> slots) => _api.call((dio) async {
        final r = await dio.put<Map<String, dynamic>>('/publish/settings', data: {'slots': slots});
        return PublishSettings.fromJson(r.data!);
      });

  Future<Result<List<PublishItem>>> queue({bool includeDone = false}) => _api.call((dio) async {
        final r = await dio.get<List<dynamic>>('/publish/queue',
            queryParameters: {'include_done': includeDone});
        return [for (final i in r.data!) PublishItem.fromJson(i as Map<String, dynamic>)];
      });

  /// Sem [shortIds]: todos os cortes 9:16 prontos do vídeo, cada um no próximo horário livre.
  Future<Result<List<PublishItem>>> schedule(String videoId,
          {List<int>? shortIds, DateTime? slotAt}) =>
      _api.call((dio) async {
        final r = await dio.post<List<dynamic>>('/publish/queue', data: {
          'video_id': videoId,
          'short_ids': ?shortIds,
          if (slotAt != null) 'slot_at': slotAt.toUtc().toIso8601String(),
        });
        return [for (final i in r.data!) PublishItem.fromJson(i as Map<String, dynamic>)];
      });

  Future<Result<PublishItem>> update(
    String id, {
    DateTime? slotAt,
    String? title,
    String? description,
    PublishStatus? status,
  }) =>
      _api.call((dio) async {
        final r = await dio.patch<Map<String, dynamic>>('/publish/queue/$id', data: {
          if (slotAt != null) 'slot_at': slotAt.toUtc().toIso8601String(),
          'title': ?title,
          'description': ?description,
          if (status != null) 'status': status.name,
        });
        return PublishItem.fromJson(r.data!);
      });

  Future<Result<void>> remove(String id) => _api.call((dio) => dio.delete<void>('/publish/queue/$id'));

  /// Envio manual ao YouTube (sem auditoria, o vídeo fica privado: serve para testar).
  Future<Result<PublishItem>> upload(String id) => _api.call((dio) async {
        final r = await dio.post<Map<String, dynamic>>('/publish/queue/$id/upload');
        return PublishItem.fromJson(r.data!);
      });

  /// URL de login do Google (a API key vai no header, não na URL aberta no navegador).
  Future<Result<Uri>> youtubeConnectUrl() => _api.call((dio) async {
        final r = await dio.get<Map<String, dynamic>>('/youtube/connect');
        return Uri.parse(r.data!['url'] as String);
      });

  Future<Result<void>> youtubeDisconnect() =>
      _api.call((dio) => dio.post<void>('/youtube/disconnect'));
}
