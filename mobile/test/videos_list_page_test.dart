import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:video_editor/core/providers.dart';
import 'package:video_editor/core/result.dart';
import 'package:video_editor/features/videos/domain/models.dart';
import 'package:video_editor/features/videos/presentation/videos_list_page.dart';
import 'package:video_editor/l10n/app_localizations.dart';

import 'models_test.dart' show loadVideoJson;

Widget wrap(Widget child, List overrides) => ProviderScope(
      overrides: [...overrides],
      retry: (_, _) => null,
      child: MaterialApp(
        locale: const Locale('pt'),
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: child,
      ),
    );

void main() {
  testWidgets('lista vídeos com o status', (tester) async {
    final video = Video.fromJson(loadVideoJson());
    await tester.pumpWidget(wrap(const VideosListPage(), [
      videosListProvider.overrideWith((ref) async => [video]),
    ]));
    await tester.pumpAndSettle();

    expect(find.text('test.mp4'), findsOneWidget);
    expect(find.textContaining('1 short'), findsOneWidget);
    expect(find.text('Enviar vídeo'), findsOneWidget);
  });

  testWidgets('mostra estado vazio', (tester) async {
    await tester.pumpWidget(wrap(const VideosListPage(), [
      videosListProvider.overrideWith((ref) async => <Video>[]),
    ]));
    await tester.pumpAndSettle();
    expect(find.textContaining('Nenhum vídeo ainda'), findsOneWidget);
  });

  testWidgets('mostra erro de API key com botão de tentar de novo', (tester) async {
    await tester.pumpWidget(wrap(const VideosListPage(), [
      videosListProvider.overrideWith(
        (ref) async => throw const FailureException(Failure(FailureKind.unauthorized)),
      ),
    ]));
    await tester.pumpAndSettle();
    expect(find.text('API key inválida.'), findsOneWidget);
    expect(find.text('Tentar de novo'), findsOneWidget);
  });
}
