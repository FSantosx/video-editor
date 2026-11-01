import 'dart:io';

import 'package:path_provider/path_provider.dart';

import '../../../core/result.dart';
import 'videos_repository.dart';

/// Baixa o MP4 de um corte para o cache do app (reaproveita se a mesma versão já foi baixada).
Future<Result<File>> cachedShortFile(
  VideosRepository repo,
  String videoId,
  int shortId,
  int version, {
  void Function(double progress)? onProgress,
}) async {
  final dir = await getTemporaryDirectory();
  final file = File('${dir.path}/short_${videoId}_${shortId}_v$version.mp4');
  if (await file.exists()) return Ok(file);
  final result = await repo.download(videoId, shortId, file.path, onProgress: onProgress);
  return switch (result) {
    Ok() => Ok(file),
    Err(:final failure) => Err(failure),
  };
}
