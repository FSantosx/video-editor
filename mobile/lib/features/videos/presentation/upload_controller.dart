import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../../../core/result.dart';
import '../domain/models.dart';

class UploadState {
  const UploadState({required this.fileName, required this.progress, this.failure});

  final String fileName;
  final double progress;
  final Failure? failure;
}

/// Upload em andamento (um por vez). Nulo quando não há upload.
class UploadController extends Notifier<UploadState?> {
  CancelToken? _cancel;

  @override
  UploadState? build() => null;

  bool get isUploading => state != null && state!.failure == null;

  /// Retorna o vídeo criado, ou nulo se falhou/cancelou (o erro fica no state).
  Future<Video?> upload(String path, String fileName) async {
    final repo = ref.read(videosRepositoryProvider);
    if (repo == null || isUploading) return null;
    _cancel = CancelToken();
    state = UploadState(fileName: fileName, progress: 0);

    final result = await repo.upload(
      path,
      fileName,
      cancelToken: _cancel,
      onProgress: (p) => state = UploadState(fileName: fileName, progress: p),
    );
    switch (result) {
      case Ok(:final value):
        state = null;
        ref.invalidate(videosListProvider);
        return value;
      case Err(:final failure):
        state = _cancel!.isCancelled
            ? null
            : UploadState(fileName: fileName, progress: 0, failure: failure);
        return null;
    }
  }

  void cancel() => _cancel?.cancel();

  void dismissError() => state = null;
}

final uploadControllerProvider =
    NotifierProvider<UploadController, UploadState?>(UploadController.new);
