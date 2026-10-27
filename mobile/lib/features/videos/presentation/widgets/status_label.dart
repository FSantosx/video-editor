import 'package:flutter/material.dart';

import '../../../../core/l10n.dart';
import '../../../../l10n/app_localizations.dart';
import '../../domain/models.dart';

String videoStatusText(AppLocalizations l10n, Video v) {
  if (v.status == VideoStatus.analyzing) {
    return switch (v.step) {
      'probe' || 'audio' => l10n.stepPreparing,
      'transcribe' => l10n.stepTranscribing,
      'analyze' => l10n.stepAnalyzing,
      'select' => l10n.stepSelecting,
      _ => l10n.statusAnalyzing,
    };
  }
  return switch (v.status) {
    VideoStatus.uploading => l10n.statusUploading,
    VideoStatus.queued => l10n.statusQueued,
    VideoStatus.analyzing => l10n.statusAnalyzing,
    VideoStatus.ready when v.shorts.isEmpty => l10n.noShortsFound,
    VideoStatus.ready when v.isBusy => l10n.statusRendering,
    VideoStatus.ready => l10n.shortsCount(v.shorts.length),
    VideoStatus.error => l10n.statusError,
  };
}

String renderStatusText(AppLocalizations l10n, ShortRender r) => switch (r.status) {
      RenderStatus.pending || RenderStatus.queued => l10n.renderQueued,
      RenderStatus.rendering => l10n.renderProgress((r.progress * 100).round()),
      RenderStatus.done => l10n.renderDone,
      RenderStatus.error => l10n.renderError,
    };

/// Barra de progresso + texto do status atual do vídeo.
class VideoProgress extends StatelessWidget {
  const VideoProgress({super.key, required this.video});

  final Video video;

  @override
  Widget build(BuildContext context) {
    final text = videoStatusText(context.l10n, video);
    return Semantics(
      label: text,
      value: '${(video.progress * 100).round()}%',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(text, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 4),
          LinearProgressIndicator(value: video.progress > 0 ? video.progress : null),
        ],
      ),
    );
  }
}
