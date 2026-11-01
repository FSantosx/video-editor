import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../core/l10n.dart';
import '../../../core/notifications.dart';
import '../../../core/providers.dart';
import '../../../core/result.dart';
import '../../../l10n/app_localizations.dart';
import '../domain/publish_models.dart';

String publishStatusText(AppLocalizations l10n, PublishItem item, DateTime now) {
  if (item.isOverdue(now)) return l10n.statusOverdue;
  return switch (item.status) {
    PublishStatus.scheduled => l10n.statusScheduled,
    PublishStatus.uploading => '${l10n.statusUploading} ${(item.progress * 100).round()}%',
    PublishStatus.uploaded =>
      item.scheduledOnYoutube ? l10n.statusScheduledOnYoutube : l10n.statusUploaded,
    PublishStatus.posted => l10n.statusPosted,
    PublishStatus.skipped => l10n.statusSkipped,
    PublishStatus.failed => l10n.statusFailed,
  };
}

Color publishStatusColor(ColorScheme cs, PublishItem item, DateTime now) {
  if (item.isOverdue(now) || item.status == PublishStatus.failed) return cs.error;
  if (item.isDone || item.sentToYoutube) return cs.primary;
  return cs.onSurfaceVariant;
}

/// "Hoje 18:00", "Amanhã 12:00" ou "seg, 03/11 21:00" no fuso do aparelho.
String formatSlot(BuildContext context, DateTime utc) {
  final l10n = context.l10n;
  final locale = Localizations.localeOf(context).toString();
  final local = utc.toLocal();
  final now = DateTime.now();
  final day = DateTime(local.year, local.month, local.day);
  final today = DateTime(now.year, now.month, now.day);
  final time = DateFormat.Hm(locale).format(local);
  if (day == today) return '${l10n.today} $time';
  if (day == today.add(const Duration(days: 1))) return '${l10n.tomorrow} $time';
  return '${DateFormat('EEE, dd/MM', locale).format(local)} $time';
}

/// Agenda cortes (um ou todos do vídeo) e avisa o resultado. Retorna se deu certo.
Future<bool> scheduleShorts(BuildContext context, WidgetRef ref, String videoId,
    {List<int>? shortIds}) async {
  final l10n = context.l10n;
  final messenger = ScaffoldMessenger.of(context);
  final repo = ref.read(publishRepositoryProvider);
  if (repo == null) return false;
  final result = await repo.schedule(videoId, shortIds: shortIds);
  if (!context.mounted) return false;
  switch (result) {
    case Ok(:final value):
      final first = value.map((i) => i.slotAt).reduce((a, b) => a.isBefore(b) ? a : b);
      messenger.showSnackBar(SnackBar(
        content: Text(l10n.scheduledMany(value.length, formatSlot(context, first))),
      ));
      if (!await PostingReminders.instance.requestPermission() && context.mounted) {
        messenger.showSnackBar(SnackBar(content: Text(l10n.remindersDenied)));
      }
      ref.invalidate(publishQueueProvider); // recarrega e refaz os lembretes
      return true;
    case Err(:final failure):
      messenger.showSnackBar(SnackBar(content: Text(failure.message(l10n))));
      return false;
  }
}
