import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/publish/data/publish_repository.dart';
import '../features/publish/domain/publish_models.dart';
import '../features/settings/data/settings_repository.dart';
import '../features/settings/domain/app_settings.dart';
import '../features/videos/data/videos_repository.dart';
import '../features/videos/domain/models.dart';
import 'api/api_client.dart';
import 'notifications.dart';
import 'result.dart';

final settingsRepositoryProvider = Provider((ref) => SettingsRepository());

class SettingsController extends AsyncNotifier<AppSettings> {
  @override
  Future<AppSettings> build() => ref.read(settingsRepositoryProvider).load();

  Future<void> save(AppSettings settings) async {
    await ref.read(settingsRepositoryProvider).save(settings);
    state = AsyncData(settings);
  }
}

final settingsProvider =
    AsyncNotifierProvider<SettingsController, AppSettings>(SettingsController.new);

/// Nulo enquanto o servidor não foi configurado.
final videosRepositoryProvider = Provider<VideosRepository?>((ref) {
  final settings = ref.watch(settingsProvider).value;
  if (settings == null || !settings.isConfigured) return null;
  return VideosRepository(ApiClient(baseUrl: settings.serverUrl, apiKey: settings.apiKey));
});

class FailureException implements Exception {
  const FailureException(this.failure);
  final Failure failure;
}

T _unwrap<T>(Result<T> result) => switch (result) {
      Ok(:final value) => value,
      Err(:final failure) => throw FailureException(failure),
    };

final videosListProvider = FutureProvider.autoDispose<List<Video>>((ref) async {
  final repo = ref.watch(videosRepositoryProvider);
  if (repo == null) return const [];
  return _unwrap(await repo.list());
});

const pollInterval = Duration(seconds: 2);

/// Detalhe do vídeo, consultando o servidor enquanto houver análise/render em andamento.
final videoDetailProvider = StreamProvider.autoDispose.family<Video, String>((ref, id) async* {
  final repo = ref.watch(videosRepositoryProvider);
  if (repo == null) throw const FailureException(Failure(FailureKind.unknown));
  var failures = 0;
  while (true) {
    final result = await repo.get(id);
    switch (result) {
      case Ok(:final value):
        failures = 0;
        yield value;
        if (!value.isBusy) return;
      case Err(:final failure):
        // Erro de rede passageiro (ex.: trocar de Wi-Fi para 4G): tenta de novo algumas vezes
        if (failure.kind != FailureKind.network || ++failures > 5) throw FailureException(failure);
    }
    await Future<void>.delayed(pollInterval);
  }
});

// ---------------------------------------------------------------- publicação

final publishRepositoryProvider = Provider<PublishRepository?>((ref) {
  final settings = ref.watch(settingsProvider).value;
  if (settings == null || !settings.isConfigured) return null;
  return PublishRepository(ApiClient(baseUrl: settings.serverUrl, apiKey: settings.apiKey));
});

/// Fila de publicação. A cada carga, os lembretes do celular são refeitos a partir dela.
final publishQueueProvider = FutureProvider.autoDispose<List<PublishItem>>((ref) async {
  final repo = ref.watch(publishRepositoryProvider);
  if (repo == null) return const [];
  final items = _unwrap(await repo.queue());
  await PostingReminders.instance.sync(items);
  return items;
});

final publishSettingsProvider = FutureProvider.autoDispose<PublishSettings>((ref) async {
  final repo = ref.watch(publishRepositoryProvider);
  if (repo == null) throw const FailureException(Failure(FailureKind.unknown));
  return _unwrap(await repo.settings());
});
