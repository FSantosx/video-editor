import 'dart:math' as math;

import 'models.dart';

/// Quanto dá para estender o trecho para antes/depois do que a IA escolheu.
const windowSlack = 30.0;

/// Edição local de um short. Só vira PATCH com o que de fato mudou.
class ShortDraft {
  const ShortDraft({
    required this.title,
    required this.hook,
    required this.start,
    required this.end,
    required this.captions,
    required this.titleOverlay,
    required this.autoReframe,
    required this.cropCenter,
    required this.cta,
    required this.ctaText,
    required this.teaser,
    required this.loop,
    required this.zoom,
  });

  factory ShortDraft.fromShort(Short s) => ShortDraft(
        title: s.title,
        hook: s.hook,
        start: s.windowStart,
        end: s.windowEnd,
        captions: s.captions,
        titleOverlay: s.titleOverlay,
        autoReframe: s.reframeMode != ReframeMode.crop || s.cropCenter == null,
        cropCenter: s.cropCenter ?? 0.5,
        cta: s.cta,
        ctaText: s.ctaText,
        teaser: s.teaser,
        loop: s.loop,
        zoom: s.zoom,
      );

  final String title;
  final String hook;
  final double start;
  final double end;
  final bool captions;
  final bool titleOverlay;
  final bool autoReframe;
  final double cropCenter;
  final bool cta;
  final String ctaText;
  final bool teaser;
  final bool loop;
  final bool zoom;

  ShortDraft copyWith({
    String? title,
    String? hook,
    double? start,
    double? end,
    bool? captions,
    bool? titleOverlay,
    bool? autoReframe,
    double? cropCenter,
    bool? cta,
    String? ctaText,
    bool? teaser,
    bool? loop,
    bool? zoom,
  }) =>
      ShortDraft(
        title: title ?? this.title,
        hook: hook ?? this.hook,
        start: start ?? this.start,
        end: end ?? this.end,
        captions: captions ?? this.captions,
        titleOverlay: titleOverlay ?? this.titleOverlay,
        autoReframe: autoReframe ?? this.autoReframe,
        cropCenter: cropCenter ?? this.cropCenter,
        cta: cta ?? this.cta,
        ctaText: ctaText ?? this.ctaText,
        teaser: teaser ?? this.teaser,
        loop: loop ?? this.loop,
        zoom: zoom ?? this.zoom,
      );

  double get length => end - start;

  ShortPatch diff(Short original) {
    final base = ShortDraft.fromShort(original);
    final windowChanged = (start - base.start).abs() > 0.05 || (end - base.end).abs() > 0.05;
    final reframeChanged = autoReframe != base.autoReframe ||
        (!autoReframe && (cropCenter - base.cropCenter).abs() > 0.005);
    return ShortPatch(
      title: title.trim() != base.title ? title.trim() : null,
      hook: normalizeHook(hook) != base.hook ? normalizeHook(hook) : null,
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
      teaser: teaser != base.teaser ? teaser : null,
      loop: loop != base.loop ? loop : null,
      zoom: zoom != base.zoom ? zoom : null,
    );
  }

  static double _round(double v) => (v * 100).round() / 100;

  /// Mesmo formato que o servidor grava: espaços simples e maiúsculas.
  static String normalizeHook(String v) => v.trim().split(RegExp(r'\s+')).join(' ').toUpperCase();
}

/// Limites do RangeSlider: o trecho atual com folga, dentro do vídeo.
({double min, double max}) windowBounds(Short s, double videoDuration) => (
      min: math.max(0, s.windowStart - windowSlack),
      max: math.min(videoDuration, s.windowEnd + windowSlack),
    );
