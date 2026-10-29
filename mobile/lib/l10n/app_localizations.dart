import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_pt.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[Locale('pt')];

  /// No description provided for @appTitle.
  ///
  /// In pt, this message translates to:
  /// **'Shorts Editor'**
  String get appTitle;

  /// No description provided for @settingsTitle.
  ///
  /// In pt, this message translates to:
  /// **'Configurações'**
  String get settingsTitle;

  /// No description provided for @settingsIntro.
  ///
  /// In pt, this message translates to:
  /// **'Informe o endereço do servidor (ex.: o domínio do Railway) e a API key definida na variável API_KEY.'**
  String get settingsIntro;

  /// No description provided for @serverUrl.
  ///
  /// In pt, this message translates to:
  /// **'URL do servidor'**
  String get serverUrl;

  /// No description provided for @invalidUrl.
  ///
  /// In pt, this message translates to:
  /// **'URL inválida'**
  String get invalidUrl;

  /// No description provided for @apiKey.
  ///
  /// In pt, this message translates to:
  /// **'API key'**
  String get apiKey;

  /// No description provided for @showKey.
  ///
  /// In pt, this message translates to:
  /// **'Mostrar chave'**
  String get showKey;

  /// No description provided for @hideKey.
  ///
  /// In pt, this message translates to:
  /// **'Ocultar chave'**
  String get hideKey;

  /// No description provided for @saveAndConnect.
  ///
  /// In pt, this message translates to:
  /// **'Salvar e conectar'**
  String get saveAndConnect;

  /// No description provided for @connectionOk.
  ///
  /// In pt, this message translates to:
  /// **'Conectado ao servidor'**
  String get connectionOk;

  /// No description provided for @errorNetwork.
  ///
  /// In pt, this message translates to:
  /// **'Sem conexão com o servidor. Verifique a internet e a URL.'**
  String get errorNetwork;

  /// No description provided for @errorUnauthorized.
  ///
  /// In pt, this message translates to:
  /// **'API key inválida.'**
  String get errorUnauthorized;

  /// No description provided for @errorNotFound.
  ///
  /// In pt, this message translates to:
  /// **'Não encontrado.'**
  String get errorNotFound;

  /// No description provided for @errorTooLarge.
  ///
  /// In pt, this message translates to:
  /// **'Arquivo grande demais para o servidor.'**
  String get errorTooLarge;

  /// No description provided for @errorInvalid.
  ///
  /// In pt, this message translates to:
  /// **'Dados inválidos.'**
  String get errorInvalid;

  /// No description provided for @errorServer.
  ///
  /// In pt, this message translates to:
  /// **'Erro no servidor.'**
  String get errorServer;

  /// No description provided for @errorUnknown.
  ///
  /// In pt, this message translates to:
  /// **'Algo deu errado.'**
  String get errorUnknown;

  /// No description provided for @retry.
  ///
  /// In pt, this message translates to:
  /// **'Tentar de novo'**
  String get retry;

  /// No description provided for @uploadVideo.
  ///
  /// In pt, this message translates to:
  /// **'Enviar vídeo'**
  String get uploadVideo;

  /// No description provided for @emptyVideos.
  ///
  /// In pt, this message translates to:
  /// **'Nenhum vídeo ainda. Envie um vídeo longo e os shorts são gerados automaticamente.'**
  String get emptyVideos;

  /// No description provided for @uploading.
  ///
  /// In pt, this message translates to:
  /// **'Enviando {fileName}'**
  String uploading(String fileName);

  /// No description provided for @uploadProgress.
  ///
  /// In pt, this message translates to:
  /// **'Progresso do envio'**
  String get uploadProgress;

  /// No description provided for @cancel.
  ///
  /// In pt, this message translates to:
  /// **'Cancelar'**
  String get cancel;

  /// No description provided for @close.
  ///
  /// In pt, this message translates to:
  /// **'Fechar'**
  String get close;

  /// No description provided for @delete.
  ///
  /// In pt, this message translates to:
  /// **'Excluir'**
  String get delete;

  /// No description provided for @deleteVideoTitle.
  ///
  /// In pt, this message translates to:
  /// **'Excluir vídeo?'**
  String get deleteVideoTitle;

  /// No description provided for @deleteVideoBody.
  ///
  /// In pt, this message translates to:
  /// **'{name} e todos os shorts gerados serão apagados do servidor.'**
  String deleteVideoBody(String name);

  /// No description provided for @statusUploading.
  ///
  /// In pt, this message translates to:
  /// **'Enviando'**
  String get statusUploading;

  /// No description provided for @statusQueued.
  ///
  /// In pt, this message translates to:
  /// **'Na fila'**
  String get statusQueued;

  /// No description provided for @statusAnalyzing.
  ///
  /// In pt, this message translates to:
  /// **'Analisando'**
  String get statusAnalyzing;

  /// No description provided for @statusRendering.
  ///
  /// In pt, this message translates to:
  /// **'Gerando shorts'**
  String get statusRendering;

  /// No description provided for @statusError.
  ///
  /// In pt, this message translates to:
  /// **'Falhou'**
  String get statusError;

  /// No description provided for @stepPreparing.
  ///
  /// In pt, this message translates to:
  /// **'Preparando o vídeo'**
  String get stepPreparing;

  /// No description provided for @stepTranscribing.
  ///
  /// In pt, this message translates to:
  /// **'Transcrevendo a fala'**
  String get stepTranscribing;

  /// No description provided for @stepAnalyzing.
  ///
  /// In pt, this message translates to:
  /// **'Analisando o áudio'**
  String get stepAnalyzing;

  /// No description provided for @stepSelecting.
  ///
  /// In pt, this message translates to:
  /// **'Escolhendo os melhores trechos'**
  String get stepSelecting;

  /// No description provided for @noShortsFound.
  ///
  /// In pt, this message translates to:
  /// **'Nenhum trecho bom encontrado'**
  String get noShortsFound;

  /// No description provided for @shortsCount.
  ///
  /// In pt, this message translates to:
  /// **'{count, plural, =1{1 short} other{{count} shorts}}'**
  String shortsCount(int count);

  /// No description provided for @renderQueued.
  ///
  /// In pt, this message translates to:
  /// **'Na fila'**
  String get renderQueued;

  /// No description provided for @renderProgress.
  ///
  /// In pt, this message translates to:
  /// **'Renderizando {percent}%'**
  String renderProgress(int percent);

  /// No description provided for @renderDone.
  ///
  /// In pt, this message translates to:
  /// **'Pronto'**
  String get renderDone;

  /// No description provided for @renderError.
  ///
  /// In pt, this message translates to:
  /// **'Erro no render'**
  String get renderError;

  /// No description provided for @shortsTitle.
  ///
  /// In pt, this message translates to:
  /// **'Shorts'**
  String get shortsTitle;

  /// No description provided for @reprocess.
  ///
  /// In pt, this message translates to:
  /// **'Reprocessar'**
  String get reprocess;

  /// No description provided for @reprocessTitle.
  ///
  /// In pt, this message translates to:
  /// **'Reprocessar cortes?'**
  String get reprocessTitle;

  /// No description provided for @reprocessBody.
  ///
  /// In pt, this message translates to:
  /// **'Os cortes deste vídeo serão gerados de novo com a versão atual (teaser, gancho, zoom e loop), sem precisar enviar o vídeo. Edições manuais nestes cortes serão perdidas.'**
  String get reprocessBody;

  /// No description provided for @outdatedBanner.
  ///
  /// In pt, this message translates to:
  /// **'Estes cortes foram gerados por uma versão antiga, sem as novidades (teaser, gancho, zoom dinâmico e final em loop).'**
  String get outdatedBanner;

  /// No description provided for @analyzingHint.
  ///
  /// In pt, this message translates to:
  /// **'Você pode fechar o app: o processamento continua no servidor.'**
  String get analyzingHint;

  /// No description provided for @editShort.
  ///
  /// In pt, this message translates to:
  /// **'Editar short'**
  String get editShort;

  /// No description provided for @savedRerendering.
  ///
  /// In pt, this message translates to:
  /// **'Salvo! Gerando a nova versão…'**
  String get savedRerendering;

  /// No description provided for @title.
  ///
  /// In pt, this message translates to:
  /// **'Título do post'**
  String get title;

  /// No description provided for @hook.
  ///
  /// In pt, this message translates to:
  /// **'Gancho (texto na tela)'**
  String get hook;

  /// No description provided for @hookHint.
  ///
  /// In pt, this message translates to:
  /// **'Até 6 palavras. Aparece no início do vídeo.'**
  String get hookHint;

  /// No description provided for @trimLabel.
  ///
  /// In pt, this message translates to:
  /// **'Trecho: {start} – {end}'**
  String trimLabel(String start, String end);

  /// No description provided for @trimHint.
  ///
  /// In pt, this message translates to:
  /// **'Pausas longas dentro do trecho são cortadas automaticamente.'**
  String get trimHint;

  /// No description provided for @captions.
  ///
  /// In pt, this message translates to:
  /// **'Legendas animadas'**
  String get captions;

  /// No description provided for @titleOverlay.
  ///
  /// In pt, this message translates to:
  /// **'Título nos primeiros segundos'**
  String get titleOverlay;

  /// No description provided for @teaser.
  ///
  /// In pt, this message translates to:
  /// **'Abertura com teaser'**
  String get teaser;

  /// No description provided for @teaserHint.
  ///
  /// In pt, this message translates to:
  /// **'Começa com o momento mais forte e volta ao início'**
  String get teaserHint;

  /// No description provided for @loop.
  ///
  /// In pt, this message translates to:
  /// **'Final em loop'**
  String get loop;

  /// No description provided for @loopHint.
  ///
  /// In pt, this message translates to:
  /// **'Termina antes do teaser e emenda no início'**
  String get loopHint;

  /// No description provided for @zoom.
  ///
  /// In pt, this message translates to:
  /// **'Zoom dinâmico'**
  String get zoom;

  /// No description provided for @zoomHint.
  ///
  /// In pt, this message translates to:
  /// **'Aproxima e afasta a cada corte'**
  String get zoomHint;

  /// No description provided for @cta.
  ///
  /// In pt, this message translates to:
  /// **'Chamada para comentar'**
  String get cta;

  /// No description provided for @ctaHint.
  ///
  /// In pt, this message translates to:
  /// **'No fim do vídeo (no meio quando o final é em loop)'**
  String get ctaHint;

  /// No description provided for @ctaText.
  ///
  /// In pt, this message translates to:
  /// **'Texto da chamada'**
  String get ctaText;

  /// No description provided for @autoReframe.
  ///
  /// In pt, this message translates to:
  /// **'Enquadramento automático'**
  String get autoReframe;

  /// No description provided for @autoReframeHint.
  ///
  /// In pt, this message translates to:
  /// **'Segue o rosto de quem fala'**
  String get autoReframeHint;

  /// No description provided for @left.
  ///
  /// In pt, this message translates to:
  /// **'Esq.'**
  String get left;

  /// No description provided for @right.
  ///
  /// In pt, this message translates to:
  /// **'Dir.'**
  String get right;

  /// No description provided for @cropPosition.
  ///
  /// In pt, this message translates to:
  /// **'Posição do recorte'**
  String get cropPosition;

  /// No description provided for @saveAndRender.
  ///
  /// In pt, this message translates to:
  /// **'Salvar e gerar de novo'**
  String get saveAndRender;

  /// No description provided for @transcript.
  ///
  /// In pt, this message translates to:
  /// **'Transcrição'**
  String get transcript;

  /// No description provided for @share.
  ///
  /// In pt, this message translates to:
  /// **'Compartilhar'**
  String get share;

  /// No description provided for @saveToGallery.
  ///
  /// In pt, this message translates to:
  /// **'Salvar na galeria'**
  String get saveToGallery;

  /// No description provided for @savedToGallery.
  ///
  /// In pt, this message translates to:
  /// **'Vídeo salvo na galeria'**
  String get savedToGallery;

  /// No description provided for @galleryPermissionDenied.
  ///
  /// In pt, this message translates to:
  /// **'Sem permissão para salvar na galeria.'**
  String get galleryPermissionDenied;

  /// No description provided for @playerError.
  ///
  /// In pt, this message translates to:
  /// **'Não foi possível reproduzir'**
  String get playerError;

  /// No description provided for @play.
  ///
  /// In pt, this message translates to:
  /// **'Reproduzir'**
  String get play;

  /// No description provided for @pause.
  ///
  /// In pt, this message translates to:
  /// **'Pausar'**
  String get pause;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['pt'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'pt':
      return AppLocalizationsPt();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
