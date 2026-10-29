import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:video_editor/features/settings/domain/app_settings.dart';
import 'package:video_editor/features/videos/domain/models.dart';
import 'package:video_editor/features/videos/domain/short_draft.dart';

/// JSON real devolvido por GET /videos/{id} (gerado pelo backend nos testes).
Map<String, dynamic> loadVideoJson() =>
    jsonDecode(File('test/fixtures/video.json').readAsStringSync()) as Map<String, dynamic>;

void main() {
  group('Video.fromJson', () {
    test('lê o JSON real da API', () {
      final video = Video.fromJson(loadVideoJson());
      expect(video.status, VideoStatus.ready);
      expect(video.meta!.isHorizontal, isTrue);
      expect(video.shorts, hasLength(1));

      final short = video.shorts.single;
      expect(short.title, 'Como sair das dívidas');
      expect(short.reframeMode, ReframeMode.crop);
      expect(short.cropCenter, 0.5);
      expect(short.render.status, RenderStatus.done);
      expect(short.render.hasFile, isTrue);
      expect(video.isBusy, isFalse);
    });

    test('status desconhecido não quebra o app', () {
      final json = loadVideoJson()..['status'] = 'algo_novo';
      expect(Video.fromJson(json).status, VideoStatus.error);
    });

    test('render em andamento deixa o vídeo ocupado', () {
      final json = loadVideoJson();
      ((json['shorts'] as List).first as Map)['render']['status'] = 'rendering';
      expect(Video.fromJson(json).isBusy, isTrue);
    });
  });

  group('ShortDraft.diff', () {
    final short = Video.fromJson(loadVideoJson()).shorts.single;

    test('sem mudanças gera patch vazio', () {
      expect(ShortDraft.fromShort(short).diff(short).isEmpty, isTrue);
    });

    test('só envia o que mudou', () {
      final draft = ShortDraft.fromShort(short).copyWith(title: '  Novo título ', captions: false);
      expect(draft.diff(short).toJson(), {'title': 'Novo título', 'captions': false});
    });

    test('mudar o trecho envia início e fim juntos', () {
      final draft = ShortDraft.fromShort(short).copyWith(end: short.windowEnd - 10);
      final json = draft.diff(short).toJson();
      expect(json.keys, containsAll(['start', 'end']));
      expect(json['end'], closeTo(short.windowEnd - 10, 0.01));
    });

    test('shorts antigos sem cta continuam funcionando', () {
      expect(short.cta, isFalse);
      expect(short.ctaText, isEmpty);
    });

    test('ligar a chamada no final envia o texto', () {
      final draft = ShortDraft.fromShort(short).copyWith(cta: true, ctaText: 'Comenta aí!');
      expect(draft.diff(short).toJson(), {'cta': true, 'cta_text': 'Comenta aí!'});
    });

    test('ligar o teaser envia só o teaser', () {
      final draft = ShortDraft.fromShort(short).copyWith(teaser: true);
      expect(short.teaser, isFalse); // fixture antigo, sem teaser
      expect(draft.diff(short).toJson(), {'teaser': true});
    });

    test('voltar ao enquadramento automático', () {
      final draft = ShortDraft.fromShort(short).copyWith(autoReframe: true);
      expect(draft.diff(short).toJson(), {'auto_reframe': true});
    });

    test('limites do trecho ficam dentro do vídeo', () {
      final b = windowBounds(short, 100);
      expect(b.min, greaterThanOrEqualTo(0));
      expect(b.max, lessThanOrEqualTo(100));
    });
  });

  group('AppSettings', () {
    test('normaliza a URL', () {
      expect(AppSettings.normalizeUrl(' meu-app.up.railway.app/ '), 'https://meu-app.up.railway.app');
      expect(AppSettings.normalizeUrl('http://192.168.0.10:8000'), 'http://192.168.0.10:8000');
      expect(AppSettings.isValidUrl(''), isFalse);
      expect(AppSettings.isValidUrl('meu-app.up.railway.app'), isTrue);
    });
  });
}
