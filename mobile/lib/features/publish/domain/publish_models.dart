/// Modelos da fila de publicação (backend/app/publish). Dart puro, sem Flutter.
library;

enum PublishStatus { scheduled, uploading, uploaded, posted, skipped, failed }

T _byName<T extends Enum>(List<T> values, Object? name, T fallback) =>
    values.where((v) => v.name == name).firstOrNull ?? fallback;

class PublishItem {
  const PublishItem({
    required this.id,
    required this.videoId,
    required this.shortId,
    required this.slotAt,
    required this.title,
    required this.description,
    required this.status,
    required this.mode,
    this.hook = '',
    this.renderVersion = 0,
    this.duration,
    this.youtubeId,
    this.error,
    this.progress = 0,
    this.scheduledOnYoutube = false,
    this.missing = false,
  });

  factory PublishItem.fromJson(Map<String, dynamic> json) => PublishItem(
        id: json['id'] as String,
        videoId: json['video_id'] as String,
        shortId: json['short_id'] as int,
        slotAt: DateTime.parse(json['slot_at'] as String).toUtc(),
        title: json['title'] as String? ?? '',
        description: json['description'] as String? ?? '',
        status: _byName(PublishStatus.values, json['status'], PublishStatus.failed),
        mode: json['mode'] as String? ?? 'assisted',
        hook: json['hook'] as String? ?? '',
        renderVersion: json['render_version'] as int? ?? 0,
        duration: (json['duration'] as num?)?.toDouble(),
        youtubeId: json['youtube_id'] as String?,
        error: json['error'] as String?,
        progress: (json['progress'] as num?)?.toDouble() ?? 0,
        scheduledOnYoutube: json['scheduled_on_youtube'] as bool? ?? false,
        missing: json['missing'] as bool? ?? false,
      );

  final String id;
  final String videoId;
  final int shortId;
  final DateTime slotAt;
  final String title;
  final String description;
  final PublishStatus status;

  /// "assisted": o app lembra e você posta; "api": o YouTube publica sozinho.
  final String mode;
  final String hook;
  final int renderVersion;
  final double? duration;
  final String? youtubeId;
  final String? error;
  final double progress;
  final bool scheduledOnYoutube;

  /// O vídeo ou o corte foi apagado depois de agendado.
  final bool missing;

  bool get isPending => status == PublishStatus.scheduled;
  bool get needsReminder => isPending && mode == 'assisted';
  bool get isDone => status == PublishStatus.posted || status == PublishStatus.skipped;
  bool get sentToYoutube => status == PublishStatus.uploaded;

  /// Atrasado: passou do horário e ainda não foi postado.
  bool isOverdue(DateTime now) => isPending && slotAt.isBefore(now);

  String? get youtubeUrl => youtubeId == null ? null : 'https://youtu.be/$youtubeId';
}

class YoutubeStatus {
  const YoutubeStatus({
    required this.configured,
    required this.connected,
    required this.audited,
    required this.autoUpload,
    this.channelTitle,
  });

  factory YoutubeStatus.fromJson(Map<String, dynamic> json) => YoutubeStatus(
        configured: json['configured'] as bool? ?? false,
        connected: json['connected'] as bool? ?? false,
        audited: json['audited'] as bool? ?? false,
        autoUpload: json['auto_upload'] as bool? ?? false,
        channelTitle: (json['channel'] as Map<String, dynamic>?)?['title'] as String?,
      );

  /// Servidor tem GOOGLE_CLIENT_ID/SECRET e PUBLIC_URL.
  final bool configured;
  final bool connected;

  /// Projeto da API aprovado na auditoria do Google (YOUTUBE_AUDITED=1).
  final bool audited;

  /// Conectado + auditado: agendar já envia com publicação programada.
  final bool autoUpload;
  final String? channelTitle;
}

class PublishSettings {
  const PublishSettings({
    required this.slots,
    required this.tz,
    required this.nextSlots,
    required this.youtube,
  });

  factory PublishSettings.fromJson(Map<String, dynamic> json) => PublishSettings(
        slots: (json['slots'] as List).cast<String>(),
        tz: json['tz'] as String,
        nextSlots: [
          for (final s in (json['next_slots'] as List? ?? const []))
            DateTime.parse(s as String).toUtc(),
        ],
        youtube: YoutubeStatus.fromJson(json['youtube'] as Map<String, dynamic>),
      );

  /// "HH:MM" no fuso [tz] (padrão America/Sao_Paulo).
  final List<String> slots;
  final String tz;
  final List<DateTime> nextSlots;
  final YoutubeStatus youtube;
}

/// Agrupa a fila por dia (no fuso local do aparelho), em ordem de horário.
Map<DateTime, List<PublishItem>> groupByDay(List<PublishItem> items) {
  final sorted = [...items]..sort((a, b) => a.slotAt.compareTo(b.slotAt));
  final out = <DateTime, List<PublishItem>>{};
  for (final item in sorted) {
    final local = item.slotAt.toLocal();
    out.putIfAbsent(DateTime(local.year, local.month, local.day), () => []).add(item);
  }
  return out;
}
