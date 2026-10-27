# Shorts Editor (app)

App Flutter que envia vídeos para o backend e mostra, toca, edita e exporta os shorts gerados.
Veja o [README principal](../README.md) para instalar e configurar.

```
lib/
  core/            cliente da API, Result, providers (Riverpod), rotas (go_router), l10n
  features/
    settings/      URL do servidor + API key (armazenamento seguro)
    videos/
      domain/      modelos e rascunho de edição: Dart puro, testado em test/models_test.dart
      data/        repositório HTTP
      presentation/ lista, detalhe (polling), editor (player + ajustes), upload
  l10n/app_pt.arb  textos (gerados com flutter gen-l10n)
```
