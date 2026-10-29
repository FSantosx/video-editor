// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Portuguese (`pt`).
class AppLocalizationsPt extends AppLocalizations {
  AppLocalizationsPt([String locale = 'pt']) : super(locale);

  @override
  String get appTitle => 'Shorts Editor';

  @override
  String get settingsTitle => 'Configurações';

  @override
  String get settingsIntro =>
      'Informe o endereço do servidor (ex.: o domínio do Railway) e a API key definida na variável API_KEY.';

  @override
  String get serverUrl => 'URL do servidor';

  @override
  String get invalidUrl => 'URL inválida';

  @override
  String get apiKey => 'API key';

  @override
  String get showKey => 'Mostrar chave';

  @override
  String get hideKey => 'Ocultar chave';

  @override
  String get saveAndConnect => 'Salvar e conectar';

  @override
  String get connectionOk => 'Conectado ao servidor';

  @override
  String get errorNetwork =>
      'Sem conexão com o servidor. Verifique a internet e a URL.';

  @override
  String get errorUnauthorized => 'API key inválida.';

  @override
  String get errorNotFound => 'Não encontrado.';

  @override
  String get errorTooLarge => 'Arquivo grande demais para o servidor.';

  @override
  String get errorInvalid => 'Dados inválidos.';

  @override
  String get errorServer => 'Erro no servidor.';

  @override
  String get errorUnknown => 'Algo deu errado.';

  @override
  String get retry => 'Tentar de novo';

  @override
  String get uploadVideo => 'Enviar vídeo';

  @override
  String get emptyVideos =>
      'Nenhum vídeo ainda. Envie um vídeo longo e os shorts são gerados automaticamente.';

  @override
  String uploading(String fileName) {
    return 'Enviando $fileName';
  }

  @override
  String get uploadProgress => 'Progresso do envio';

  @override
  String get cancel => 'Cancelar';

  @override
  String get close => 'Fechar';

  @override
  String get delete => 'Excluir';

  @override
  String get deleteVideoTitle => 'Excluir vídeo?';

  @override
  String deleteVideoBody(String name) {
    return '$name e todos os shorts gerados serão apagados do servidor.';
  }

  @override
  String get statusUploading => 'Enviando';

  @override
  String get statusQueued => 'Na fila';

  @override
  String get statusAnalyzing => 'Analisando';

  @override
  String get statusRendering => 'Gerando shorts';

  @override
  String get statusError => 'Falhou';

  @override
  String get stepPreparing => 'Preparando o vídeo';

  @override
  String get stepTranscribing => 'Transcrevendo a fala';

  @override
  String get stepAnalyzing => 'Analisando o áudio';

  @override
  String get stepSelecting => 'Escolhendo os melhores trechos';

  @override
  String get noShortsFound => 'Nenhum trecho bom encontrado';

  @override
  String shortsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count shorts',
      one: '1 short',
    );
    return '$_temp0';
  }

  @override
  String get renderQueued => 'Na fila';

  @override
  String renderProgress(int percent) {
    return 'Renderizando $percent%';
  }

  @override
  String get renderDone => 'Pronto';

  @override
  String get renderError => 'Erro no render';

  @override
  String get shortsTitle => 'Shorts';

  @override
  String get reprocess => 'Reprocessar';

  @override
  String get reprocessTitle => 'Reprocessar cortes?';

  @override
  String get reprocessBody =>
      'Os cortes deste vídeo serão gerados de novo com a versão atual (teaser, gancho, zoom e loop), sem precisar enviar o vídeo. Edições manuais nestes cortes serão perdidas.';

  @override
  String get outdatedBanner =>
      'Estes cortes foram gerados por uma versão antiga, sem as novidades (teaser, gancho, zoom dinâmico e final em loop).';

  @override
  String get analyzingHint =>
      'Você pode fechar o app: o processamento continua no servidor.';

  @override
  String get editShort => 'Editar short';

  @override
  String get savedRerendering => 'Salvo! Gerando a nova versão…';

  @override
  String get title => 'Título do post';

  @override
  String get hook => 'Gancho (texto na tela)';

  @override
  String get hookHint => 'Até 6 palavras. Aparece no início do vídeo.';

  @override
  String trimLabel(String start, String end) {
    return 'Trecho: $start – $end';
  }

  @override
  String get trimHint =>
      'Pausas longas dentro do trecho são cortadas automaticamente.';

  @override
  String get captions => 'Legendas animadas';

  @override
  String get titleOverlay => 'Título nos primeiros segundos';

  @override
  String get teaser => 'Abertura com teaser';

  @override
  String get teaserHint => 'Começa com o momento mais forte e volta ao início';

  @override
  String get loop => 'Final em loop';

  @override
  String get loopHint => 'Termina antes do teaser e emenda no início';

  @override
  String get zoom => 'Zoom dinâmico';

  @override
  String get zoomHint => 'Aproxima e afasta a cada corte';

  @override
  String get cta => 'Chamada para comentar';

  @override
  String get ctaHint => 'No fim do vídeo (no meio quando o final é em loop)';

  @override
  String get ctaText => 'Texto da chamada';

  @override
  String get autoReframe => 'Enquadramento automático';

  @override
  String get autoReframeHint => 'Segue o rosto de quem fala';

  @override
  String get left => 'Esq.';

  @override
  String get right => 'Dir.';

  @override
  String get cropPosition => 'Posição do recorte';

  @override
  String get saveAndRender => 'Salvar e gerar de novo';

  @override
  String get transcript => 'Transcrição';

  @override
  String get share => 'Compartilhar';

  @override
  String get saveToGallery => 'Salvar na galeria';

  @override
  String get savedToGallery => 'Vídeo salvo na galeria';

  @override
  String get galleryPermissionDenied => 'Sem permissão para salvar na galeria.';

  @override
  String get playerError => 'Não foi possível reproduzir';

  @override
  String get play => 'Reproduzir';

  @override
  String get pause => 'Pausar';
}
