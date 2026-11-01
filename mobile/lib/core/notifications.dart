import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import '../features/publish/domain/publish_models.dart';

/// Lembretes de postagem agendados no próprio celular.
///
/// Não dependem do servidor (que dorme no Railway) nem de push: a cada vez que a fila é
/// carregada, os lembretes são refeitos a partir dela (fonte da verdade = servidor).
class PostingReminders {
  PostingReminders._();

  static final instance = PostingReminders._();

  final _plugin = FlutterLocalNotificationsPlugin();
  bool _ready = false;

  static const _channel = AndroidNotificationDetails(
    'posting_reminders',
    'Hora de postar',
    channelDescription: 'Avisa no horário agendado de cada corte',
    importance: Importance.high,
    priority: Priority.high,
  );

  /// [onTap] recebe o id do item da fila (abre a tela de postagem).
  Future<void> init({required void Function(String itemId) onTap}) async {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) return;
    try {
      tzdata.initializeTimeZones();
      await _plugin.initialize(
        settings: const InitializationSettings(
          android: AndroidInitializationSettings('@mipmap/ic_launcher'),
        ),
        onDidReceiveNotificationResponse: (r) {
          if (r.payload != null) onTap(r.payload!);
        },
      );
      _ready = true;
      // App aberto pelo toque num lembrete (estava fechado)
      final launch = await _plugin.getNotificationAppLaunchDetails();
      final payload = launch?.notificationResponse?.payload;
      if ((launch?.didNotificationLaunchApp ?? false) && payload != null) onTap(payload);
    } catch (e) {
      debugPrint('lembretes indisponíveis: $e');
    }
  }

  /// true se pode notificar (ou se não há lembretes nesta plataforma: nada a pedir).
  Future<bool> requestPermission() async {
    if (!_ready) return true;
    final android =
        _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
    return await android?.requestNotificationsPermission() ?? true;
  }

  /// Refaz todos os lembretes a partir da fila (só itens do modo assistido, no futuro).
  Future<void> sync(List<PublishItem> items) async {
    if (!_ready) return;
    try {
      await _plugin.cancelAllPendingNotifications();
      final now = DateTime.now().toUtc();
      for (final item in remindersFor(items, now)) {
        await _plugin.zonedSchedule(
          id: notificationId(item.id),
          scheduledDate: tz.TZDateTime.from(item.slotAt, tz.UTC),
          notificationDetails: const NotificationDetails(android: _channel),
          // inexato: dispensa a permissão de alarme exato (pode atrasar alguns minutos)
          androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
          title: 'Hora de postar 🎬',
          body: item.title,
          payload: item.id,
        );
      }
    } catch (e) {
      debugPrint('falha ao agendar lembretes: $e');
    }
  }
}

/// Itens que precisam de lembrete: modo assistido, ainda não postados e no futuro.
List<PublishItem> remindersFor(List<PublishItem> items, DateTime nowUtc) =>
    [for (final i in items) if (i.needsReminder && i.slotAt.isAfter(nowUtc)) i];

/// Id numérico estável (o plugin exige int de 32 bits) a partir do id do item.
int notificationId(String itemId) {
  var h = 0;
  for (final c in itemId.codeUnits) {
    h = (h * 31 + c) & 0x7fffffff;
  }
  return h;
}
