# Roadmap e histórico

Documento para retomar o projeto: o que já existe, as decisões tomadas e os próximos passos,
com os arquivos envolvidos e como validar cada item.

## Estado atual (MVP, outubro de 2026)

Funcionando em produção:

- **Backend** (`backend/`) no Railway: `https://video-editor-production-2735.up.railway.app`
  - faster-whisper (`base`, CPU int8) → seleção heurística → corte de pausas e bastidor →
    reenquadramento 9:16 (OpenCV Haar) → legendas ASS → render ffmpeg
  - API com upload, progresso, edição por PATCH (re-render) e download
- **App Android** (`mobile/`, Flutter 3.47.8): upload, acompanhamento, player, edição, galeria e
  compartilhamento
- **CI** (`.github/workflows/`): testes do backend e build Docker; testes do app e APK
  (artefato `shorts-editor-apk`); validação do devcontainer
- **Codespaces** (`.devcontainer/`): ambiente com Flutter e Android SDK para gerar o APK

### Decisões tomadas

| Decisão | Motivo |
|---|---|
| App + servidor, em vez de tudo no celular | Transcrição e render no celular seriam lentos e esquentariam o aparelho; o ffmpeg-kit foi descontinuado |
| Seleção sem LLM no MVP | Simplicidade e custo zero; `select_shorts()` tem a interface pronta para trocar |
| JSON de edição como fonte da verdade | Edição não destrutiva: o app altera o JSON e o servidor re-renderiza |
| Um único ffmpeg por short (`-ss` por clip + concat + legendas) | Uma só codificação: mais rápido e sem perda de qualidade entre etapas |
| OpenCV 4.x (não 5) | O OpenCV 5 removeu o `CascadeClassifier` |
| Áudio entregue ao Whisper como array numpy | O faster-whisper 1.2.1 chama `av.open(metadata_errors=...)`, parâmetro removido no PyAV 19 |
| Fila de jobs em threads, estado em JSON no volume `/data` | Suficiente para um container; os jobs são retomados após restart |
| `API_KEY` própria (não é chave do Claude) | Protege a API pública; uma eventual chave de LLM fica só no servidor |

### Problemas já resolvidos

- O `equalizeHist` piorava a detecção de rosto: foi removido, e a detecção roda em 960px de largura.
- Os shorts incluíam frases de bastidor ("bom, deixa eu ajustar a câmera"): agora são cortadas do
  meio do trecho, e as janelas que atravessam pausas longas (troca de assunto) são penalizadas.
- A transcrição falhava com `open() got an unexpected keyword argument 'metadata_errors'`
  (ver tabela acima).

---

## Próximas evoluções (por impacto)

### 1. Seleção de trechos com LLM ⭐ maior ganho de qualidade

**Problema:** a heurística (ritmo, energia do áudio, palavras de gancho) não entende o conteúdo.
**Onde:** `backend/app/pipeline/select.py`, na função `select_shorts(words, energy, ...)`.

Abordagem:
- Criar `select_llm.py` com a mesma assinatura e escolher o seletor pela variável
  `SELECTOR=heuristic|llm`.
- Enviar ao modelo a transcrição em frases, com `[início-fim]` e o índice de cada uma. Pedir via
  tool use / structured output uma lista de `{first_sentence, last_sentence, skip_sentences[],
  title, hook, score, reason}`.
- Validar no código: duração entre 30 e 60s após `speech_duration`, sem sobreposição, e encaixe
  nas fronteiras de frase. Converter `skip_sentences` em `segments`, porque `build_short` já os aceita.
- Vídeos longos (mais de 1h): mandar a transcrição em blocos com sobreposição, ou fazer uma
  pré-seleção heurística e enviar só os melhores candidatos ao LLM.
- Gerar também um título de gancho melhor (hoje é a primeira frase cortada).
- Se a API do LLM falhar, cair para a heurística.

Configuração: `ANTHROPIC_API_KEY` **só no Railway** (nunca no app). Usar o modelo Claude
mais recente disponível.
Validar: um teste com o LLM mockado (como `tests/test_transcribe.py` faz com o Whisper) e uma
comparação manual com a heurística no mesmo vídeo.

### 2. Reenquadramento melhor

**Problema:** o Haar falha com rosto de perfil ou pequeno e não sabe quem está falando.
**Onde:** `backend/app/pipeline/reframe.py`, na função `compute_reframe()`.

Abordagem:
- Trocar por MediaPipe Face Detection ou YuNet (`cv2.FaceDetectorYN`). O modelo ONNX tem
  cerca de 300 KB e pode ser baixado no build do Docker.
- Falante ativo: cruzar os rostos com a diarização (WhisperX) ou com o movimento da boca.
- Acompanhamento suave dentro do clip (hoje o centro é fixo por clip): interpolar e suavizar
  com média móvel, aplicando via `sendcmd`/`crop` com expressão no ffmpeg.
- Dois rostos distantes: dividir a tela (um em cima, outro embaixo).

Validar: `tools/make_test_video.py` já gera um rosto que muda de posição; acrescentar um caso
de perfil e um com duas pessoas.

### 3. Velocidade em vídeos longos

**Problema:** um vídeo de 57 minutos na CPU do Railway leva dezenas de minutos na transcrição.
**Onde:** `backend/app/pipeline/transcribe.py` e `backend/app/config.py`.

Opções, da mais simples para a mais complexa:
- Medir antes: registrar no `video.json` o tempo de cada etapa (já existe `analysis_seconds`).
- `WHISPER_MODEL=tiny` ou `base` para a seleção, retranscrevendo só os trechos escolhidos com
  `small` para as legendas.
- Paralelizar por blocos de áudio (`WORKERS`, `cpu_threads` do CTranslate2).
- GPU sob demanda (Modal, Replicate ou RunPod) só para a transcrição, mantendo o resto no Railway.
- Mostrar no app uma estimativa de tempo restante.

### 4. Estilos de legenda no app

**Onde:** `backend/app/pipeline/captions.py` (estilos ASS) e no app, no editor
(`mobile/lib/features/videos/presentation/short_editor_page.dart`).

- Presets (amarelo/branco, caixa de fundo, fonte, tamanho, posição) guardados no JSON do short
  (`captions.style`) e aceitos no PATCH.
- Destaque automático de palavras-chave e números; emojis opcionais.
- Fontes extras no Dockerfile (Montserrat, Poppins) com `fontsdir` no filtro `subtitles`.
- Editar o texto das legendas (corrigir erros da transcrição), salvando por palavra no JSON.

### 5. Limpeza automática do armazenamento

**Problema:** o volume do Railway enche com os vídeos originais.
**Onde:** `backend/app/jobs.py` e `backend/app/store.py`.

- Tarefa periódica (thread no `lifespan`) que apaga o `source.*` depois de N dias
  (`RETENTION_DAYS`), mantendo os shorts e a análise. A edição de trecho fica bloqueada depois disso.
- Mostrar o espaço livre (`GET /stats` já existe) e alertar no app.

### Manutenção pendente

- [ ] Atualizar as actions para versões com Node 24 (`actions/checkout@v5`,
  `actions/setup-java@v5`, `actions/upload-artifact@v5`): hoje geram aviso de depreciação.
- [ ] `ubuntu-latest` vai migrar para o Ubuntu 26: conferir se o `setup.sh` e os workflows continuam passando.
- [ ] Chave de release para a Play Store (hoje o APK é assinado com a chave de debug).
- [ ] Fila de jobs com Redis/RQ se um dia houver mais de uma instância do servidor.

## Como retomar

1. Abrir um codespace (ou clonar) e rodar os testes: `cd backend && python -m pytest -q`
   e `cd mobile && flutter test`.
2. Escolher um item acima e criar uma branch.
3. Testar localmente com o vídeo sintético (`backend/tools/make_test_video.py`) e com um vídeo
   real no Railway.
