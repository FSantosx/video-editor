import 'dart:math' as math;

import 'models.dart';

/// Quanto dá para estender o trecho para antes/depois do que a IA escolheu.
const windowSlack = 30.0;

/// Edição local de um short. Só vira PATCH com o que de fato mudou.
class ShortDraft {
  const ShortDraft({
    required this.title,
    required this.start,
    required this.end,
    required this.captions,
    required this.titleOverlay,
    required this.autoReframe,
    required this.cropCenter,
    required this.cta,
    required this.ctaText,
  });

  factory ShortDraft.fromShort(Short s) => ShortDraft(
        title: s.title,
        start: s.windowStart,
        end: s.windowEnd,
        captions: s.captions,
        titleOverlay: s.titleOverlay,
        autoReframe: s.reframeMode != ReframeMode.crop || s.cropCenter == null,
        cropCenter: s.cropCenter ?? 0.5,
        cta: s.cta,
        ctaText: s.ctaText,
      );

  final String title;
  final double start;
  final double end;
  final bool captions;
  final bool titleOverlay;
  final bool autoReframe;
  final double cropCenter;
  final bool cta;
  final String ctaText;

  ShortDraft copyWith({
    String? title,
    double? start,
    double? end,
    bool? captions,
    bool? titleOverlay,
    bool? autoReframe,
    double? cropCenter,
    bool? cta,
    String? ctaText,
  }) =>
      ShortDraft(
        title: title ?? this.title,
        start: start ?? this.start,
        end: end ?? this.end,
        captions: captions ?? this.captions,
        titleOverlay: titleOverlay ?? this.titleOverlay,
        autoReframe: autoReframe ?? this.autoReframe,
        cropCenter: cropCenter ?? this.cropCenter,
        cta: cta ?? this.cta,
        ctaText: ctaText ?? this.ctaText,
      );

  double get length => end - start;

  ShortPatch diff(Short original) {
    final base = ShortDraft.fromShort(original);
    final windowChanged = (start - base.start).abs() > 0.05 || (end - base.end).abs() > 0.05;
    final reframeChanged = autoReframe != base.autoReframe ||
        (!autoReframe && (cropCenter - base.cropCenter).abs() > 0.005);
    return ShortPatch(
      title: title.trim() != base.title ? title.trim() : null,
      start: windowChanged ? _round(start) : null,
      end: windowChanged ? _round(end) : null,
      captions: captions != base.captions ? captions : null,
      titleOverlay: titleOverlay != base.titleOverlay ? titleOverlay : null,
      autoReframe: reframeChanged && autoReframe ? true : null,
      cropCenter: reframeChanged && !autoReframe ? _round(cropCenter) : null,
      cta: cta != base.cta ? cta : null,
      ctaText: cta && ctaText.trim().isNotEmpty && ctaText.trim() != base.ctaText
          ? ctaText.trim()
          : null,
    );
  }

  static double _round(double v) => (v * 100).round() / 100;
}

/// Limites do RangeSlider: o trecho atual com folga, dentro do vídeo.
({double min, double max}) windowBounds(Short s, double videoDuration) => (
      min: math.max(0, s.windowStart - windowSlack),
      max: math.min(videoDuration, s.windowEnd + windowSlack),
    );
