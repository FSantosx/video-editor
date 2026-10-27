import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'core/providers.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Riverpod 3 refaz providers com erro automaticamente; aqui o usuário decide (botão "tentar de novo")
  final container = ProviderContainer(retry: (_, _) => null);
  // Carrega as configurações antes do primeiro frame para o redirect do router funcionar
  await container.read(settingsProvider.future);
  runApp(UncontrolledProviderScope(container: container, child: const VideoEditorApp()));
}
