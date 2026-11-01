import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'core/notifications.dart';
import 'core/providers.dart';
import 'core/result.dart';
import 'core/router.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Riverpod 3 refaz providers com erro automaticamente; aqui o usuário decide (botão "tentar de novo")
  final container = ProviderContainer(retry: (_, _) => null);
  // Carrega as configurações antes do primeiro frame para o redirect do router funcionar
  await container.read(settingsProvider.future);
  // Toque no lembrete "Hora de postar" abre a tela de postagem daquele corte
  await PostingReminders.instance.init(onTap: (itemId) {
    WidgetsBinding.instance.addPostFrameCallback(
        (_) => container.read(routerProvider).push('/publish/$itemId'));
  });
  runApp(UncontrolledProviderScope(container: container, child: const VideoEditorApp()));
  unawaited(_syncReminders(container));
}

/// Refaz os lembretes a partir da fila do servidor sempre que o app abre.
Future<void> _syncReminders(ProviderContainer container) async {
  final repo = container.read(publishRepositoryProvider);
  if (repo == null) return;
  if (await repo.queue() case Ok(:final value)) {
    await PostingReminders.instance.sync(value);
  }
}
