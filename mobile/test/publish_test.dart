import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:video_editor/core/notifications.dart';
import 'package:video_editor/core/providers.dart';
import 'package:video_editor/features/publish/domain/publish_models.dart';
import 'package:video_editor/features/publish/presentation/agenda_page.dart';
import 'package:video_editor/l10n/app_localizations.dart';

Map<String, dynamic> itemJson({
  String id = 'a1',
  String slot = '2030-01-02T21:00:00Z',
  String status = 'scheduled',
  String mode = 'assisted',
}) =>
    {
      'id': id,
      'video_id': 'v1',
      'short_id': 1,
      'slot_at': slot,
      'title': 'O erro que custou a eleição',
      'description': 'desc #shorts',
      'tags': ['campanha'],
      'status': status,
      'mode': mode,
      'youtube_id': null,
      'error': null,
      'hook': 'O ERRO',
      'render_version': 2,
      'duration': 38.5,
    };

void main() {
  group('PublishItem', () {
    test('lê o JSON da fila (backend/app/publish)', () {
      final item = PublishItem.fromJson(itemJson());
      expect(item.slotAt, DateTime.utc(2030, 1, 2, 21));
      expect(item.status, PublishStatus.scheduled);
      expect(item.needsReminder, isTrue);
      expect(item.renderVersion, 2);
    });

    test('status desconhecido vira falha, sem quebrar', () {
      expect(PublishItem.fromJson(itemJson(status: 'novo')).status, PublishStatus.failed);
    });

    test('atrasado = agendado e com horário no passado', () {
      final item = PublishItem.fromJson(itemJson(slot: '2020-01-01T15:00:00Z'));
      expect(item.isOverdue(DateTime.now().toUtc()), isTrue);
      final posted = PublishItem.fromJson(itemJson(slot: '2020-01-01T15:00:00Z', status: 'posted'));
      expect(posted.isOverdue(DateTime.now().toUtc()), isFalse);
    });
  });

  test('lembretes: só modo assistido, pendente e no futuro', () {
    final now = DateTime.utc(2030, 1, 1);
    final items = [
      PublishItem.fromJson(itemJson(id: 'ok')),
      PublishItem.fromJson(itemJson(id: 'passado', slot: '2029-12-31T21:00:00Z')),
      PublishItem.fromJson(itemJson(id: 'postado', status: 'posted')),
      PublishItem.fromJson(itemJson(id: 'api', mode: 'api', status: 'uploaded')),
    ];
    expect(remindersFor(items, now).map((i) => i.id), ['ok']);
  });

  test('id numérico do lembrete é estável e cabe em 32 bits', () {
    expect(notificationId('abc123'), notificationId('abc123'));
    expect(notificationId('abc123'), isNot(notificationId('abc124')));
    expect(notificationId('f' * 40), lessThan(1 << 31));
  });

  test('agrupa por dia em ordem de horário', () {
    final groups = groupByDay([
      PublishItem.fromJson(itemJson(id: 'b', slot: '2030-01-03T15:00:00Z')),
      PublishItem.fromJson(itemJson(id: 'a', slot: '2030-01-02T15:00:00Z')),
      PublishItem.fromJson(itemJson(id: 'c', slot: '2030-01-02T18:00:00Z')),
    ]);
    expect(groups.length, 2);
    expect(groups.values.first.map((i) => i.id), ['a', 'c']);
  });

  Widget app(List<PublishItem> items) => ProviderScope(
        overrides: [publishQueueProvider.overrideWith((ref) async => items)],
        retry: (_, _) => null,
        child: const MaterialApp(
          locale: Locale('pt'),
          localizationsDelegates: [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          supportedLocales: AppLocalizations.supportedLocales,
          home: AgendaPage(),
        ),
      );

  testWidgets('agenda mostra itens e marca os atrasados', (tester) async {
    await tester.pumpWidget(app([
      PublishItem.fromJson(itemJson()),
      PublishItem.fromJson(itemJson(id: 'old', slot: '2020-01-01T15:00:00Z')),
    ]));
    await tester.pumpAndSettle();
    expect(find.text('O erro que custou a eleição'), findsNWidgets(2));
    expect(find.textContaining('Atrasado'), findsOneWidget);
  });

  testWidgets('agenda vazia explica como agendar', (tester) async {
    await tester.pumpWidget(app(const []));
    await tester.pumpAndSettle();
    expect(find.textContaining('Nada agendado'), findsOneWidget);
  });
}
