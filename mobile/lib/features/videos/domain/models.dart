/// Modelos espelhando o JSON da API (backend/app/main.py). Dart puro, sem Flutter.
library;

enum VideoStatus { uploading, queued, analyzing, ready, error }

enum RenderStatus { pending, queued, rendering, done, error }

enum ReframeMode { auto, crop, fit, blur }

T _enumByName<T extends Enum>(List<T> values, Object? name, T fallback) =>
    values.where((v) => v.name == name).firstOrNull ?? fallback;

double _toDouble(Object? v) => (v as num?)?.toDouble() ?? 0;

class VideoMeta {
  const VideoMeta({required this.width, required this.height, required this.duration});

  factory VideoMeta.fromJson(Map<String, dynamic> json) => VideoMeta(
        width: json['width'] as int,
        height: json['height'] as int,
        duration: _toDouble(json['duration']),
      );

  final int width;
  final int height;
  final double duration;

  /// Só vídeos horizontais podem ter o recorte ajustado.
  bool get isHorizontal => width / height > 9 / 16 + 0.01;
}

class ShortRender {
  const ShortRender({
    required this.status,
    required this.progress,
    required this.version,
    this.error,
  });

  factory ShortRender.fromJson(Map<String, dynamic> json) => ShortRender(
        status: _enumByName(RenderStatus.values, json['status'], RenderStatus.pending),
        progress: _toDouble(json['progress']),
        version: json['version'] as int? ?? 0,
        error: json['error'] as String?,
      );

  final RenderStatus status;
  final double progress;

  /// Incrementa a cada render: usado para não tocar um MP4 antigo do cache.
  final int version;
  final String? error;

  bool get isWorking =>
      status == RenderStatus.pending ||
      status == RenderStatus.queued ||
      status == RenderStatus.rendering;

  /// Existe um MP4 pronto (talvez de uma versão anterior, se estiver re-renderizando).
  bool get hasFile => version > 0;
}

class Short {
  const Short({
    required this.id,
    required this.title,
    required this.score,
    required this.text,
    required this.windowStart,
    required this.windowEnd,
    required this.duration,
    required this.clipCount,
    required this.reframeMode,
    required this.cropCenter,
    required this.captions,
    required this.titleOverlay,
    required this.cta,
    required this.ctaText,
    required this.render,
  });

  factory Short.fromJson(Map<String, dynamic> json) {
    final window = json['window'] as Map<String, dynamic>;
    final reframe = json['reframe'] as Map<String, dynamic>;
    final centers = (reframe['centers'] as List).cast<num>();
    final cta = json['cta'] as Map<String, dynamic>?; // ausente em shorts antigos
    return Short(
      id: json['id'] as int,
      title: json['title'] as String,
      score: json['score'] as int? ?? 0,
      text: json['text'] as String? ?? '',
      windowStart: _toDouble(window['start']),
      windowEnd: _toDouble(window['end']),
      duration: _toDouble(json['duration']),
      clipCount: (json['clips'] as List).length,
      reframeMode: _enumByName(ReframeMode.values, reframe['mode'], ReframeMode.auto),
      cropCenter: centers.isEmpty ? null : centers.first.toDouble(),
      captions: (json['captions'] as Map<String, dynamic>)['enabled'] as bool,
      titleOverlay: (json['title_overlay'] as Map<String, dynamic>)['enabled'] as bool,
      cta: cta?['enabled'] as bool? ?? false,
      ctaText: cta?['text'] as String? ?? '',
      render: ShortRender.fromJson(json['render'] as Map<String, dynamic>),
    );
  }

  final int id;
  final String title;
  final int score;
  final String text;
  final double windowStart;
  final double windowEnd;
  final double duration;
  final int clipCount;
  final ReframeMode reframeMode;
  final double? cropCenter;
  final bool captions;
  final bool titleOverlay;

  /// Chamada no final (ex.: "E você, o que acha? Comenta aí!")
  final bool cta;
  final String ctaText;
  final ShortRender render;
}

class Video {
  const Video({
    required this.id,
    required this.filename,
    required this.createdAt,
    required this.status,
    required this.progress,
    required this.shorts,
    this.step,
    this.error,
    this.meta,
  });

  factory Video.fromJson(Map<String, dynamic> json) => Video(
        id: json['id'] as String,
        filename: json['filename'] as String,
        createdAt: DateTime.fromMillisecondsSinceEpoch(
          (_toDouble(json['created_at']) * 1000).round(),
        ),
        status: _enumByName(VideoStatus.values, json['status'], VideoStatus.error),
        step: json['step'] as String?,
        progress: _toDouble(json['progress']),
        error: json['error'] as String?,
        meta: json['meta'] == null
            ? null
            : VideoMeta.fromJson(json['meta'] as Map<String, dynamic>),
        shorts: [
          for (final s in (json['shorts'] as List? ?? const []))
            Short.fromJson(s as Map<String, dynamic>),
        ],
      );

  final String id;
  final String filename;
  final DateTime createdAt;
  final VideoStatus status;
  final String? step;
  final double progress;
  final String? error;
  final VideoMeta? meta;
  final List<Short> shorts;

  bool get isAnalyzing =>
      status == VideoStatus.uploading ||
      status == VideoStatus.queued ||
      status == VideoStatus.analyzing;

  /// Ainda há algo mudando no servidor: vale continuar consultando.
  bool get isBusy => isAnalyzing || shorts.any((s) => s.render.isWorking);
}

/// Alterações enviadas no PATCH; campos nulos não são enviados.
class ShortPatch {
  const ShortPatch({
    this.title,
    this.start,
    this.end,
    this.captions,
    this.titleOverlay,
    this.cropCenter,
    this.autoReframe,
    this.cta,
    this.ctaText,
  });

  final String? title;
  final double? start;
  final double? end;
  final bool? captions;
  final bool? titleOverlay;
  final double? cropCenter;
  final bool? autoReframe;
  final bool? cta;
  final String? ctaText;

  Map<String, dynamic> toJson() => {
        if (title != null) 'title': title,
        if (start != null) 'start': start,
        if (end != null) 'end': end,
        if (captions != null) 'captions': captions,
        if (titleOverlay != null) 'title_overlay': titleOverlay,
        if (cropCenter != null) 'crop_center': cropCenter,
        if (autoReframe != null) 'auto_reframe': autoReframe,
        if (cta != null) 'cta': cta,
        if (ctaText != null) 'cta_text': ctaText,
      };

  bool get isEmpty => toJson().isEmpty;
}
