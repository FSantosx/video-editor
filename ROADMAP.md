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
- **Desktop Windows** (`desktop/`): mesmo backend rodando local com GPU (Whisper `large-v3-turbo`
  em CUDA, render com NVENC), interface web em `localhost:8765`, cortes **9:16 e 1:1** por trecho
  (ligados por `group`, editáveis juntos com `sync_group`); instalador com autoteste; CI em Windows

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
| Desktop reaproveita o `backend/` (sem fork) | Uma melhoria no pipeline vale para PC, servidor e app ao mesmo tempo |
| Um short por formato, ligados por `group` | O app Android continua igual; no PC dá para editar os formatos juntos ou separados |
| MP4 com versão no nome (`short_1_v2.mp4`) | No Windows não dá para sobrescrever um arquivo aberto no player; também evita cache velho |
| Fallback do ffmpeg para ler frames | O OpenCV não abre caminhos acentuados no Windows (`C:\Users\Fábio`) |

### Problemas já resolvidos

- O `equalizeHist` piorava a detecção de rosto: foi removido, e a detecção roda em 960px de largura.
- Os shorts incluíam frases de bastidor ("bom, deixa eu ajustar a câmera"): agora são cortadas do
  meio do trecho, e as janelas que atravessam pausas longas (troca de assunto) são penalizadas.
- A transcrição falhava com `open() got an unexpected keyword argument 'metadata_errors'`
  (ver tabela acima).

### Feedback de performance (YouTube)

| Data | Corte | Duração | Ficaram para assistir | Retenção média | Ajustes feitos |
|---|---|---|---|---|---|
| 2026-10-28 | "Renan fala de seus arrependimentos da campanha" (62 views) | 55s | 62,3% (gancho bom) | 0:26 (48,8%) | Alvo de duração 38s (`SHORT_TARGET_S`), pausas cortadas a partir de 0,25s (antes 0,35s), seleção premia final conclusivo e pune final pendurado ou "rabo fraco", chamada para comentar nos últimos 3s (`CTA_*`) |

Próximo passo: comparar a retenção média dos cortes gerados depois desses ajustes. A meta é
passar de 60% de retenção média e manter "ficaram para assistir" acima de 60%. Amostras pequenas
(menos de 500 views) oscilam muito; olhar a média de vários cortes.

---

## Meta do canal: monetização (YouTube Partner Program)

Definida em 2026-10-29. Requisitos segundo fontes de mercado (air.io, vidIQ); **confirmar em
YouTube Studio → Ganhar dinheiro**, porque os números mudam.

| Etapa | Requisito | Prazo |
|---|---|---|
| **1. YPP inicial** (membros, Super Thanks, compras) | 500 inscritos + **3 milhões** de visualizações de Shorts em 90 dias + 3 uploads | **27/01/2027** |
| **2. Anúncios** | 1.000 inscritos + **10 milhões** de visualizações de Shorts em 90 dias | Fontes indicam que sobe para **20 milhões a partir de 01/02/2027** |

Contar **visualizações intencionais** (engaged views), não as visualizações totais.

### Ponto de partida (corte postado em 28/10, primeiras 24h)

| Métrica | Valor | Meta |
|---|---|---|
| Visualizações intencionais/dia | 592 (1.220 totais) | **33 mil/dia** |
| Continuaram assistindo | 56,2% | ≥ 65% |
| % assistida média | 65,2% (0:35) | ≥ 70% |
| Inscritos | 1 a cada ~600 visualizações intencionais | manter |

O gargalo é **volume de visualizações**: na taxa atual, 3 milhões de visualizações trariam
inscritos de sobra. O ponto fraco da qualidade é o **início** (44% deslizam).

### Plano

- **Volume:** 2 a 3 Shorts por dia (cerca de 200 em 90 dias); média de 11 a 17 mil visualizações
  intencionais por Short. De 1 a 2 vídeos-fonte por semana bastam, porque o pipeline gera até 8 cortes.
- **Qualidade:** abrir na frase mais forte, com título curto na tela (gancho do 1º segundo);
  cortes de ~38s; final conclusivo + chamada para comentar.
- **Marcos (visualizações intencionais/dia):** semana 2 → 5 mil · semana 4 → 15 mil ·
  semana 8 → 33 mil · semana 12 → 50 mil. Se ficar abaixo por 2 semanas seguidas, mudar o
  tema ou a fonte dos cortes.
- **Risco: conteúdo reutilizado.** Canais de cortes de terceiros são recusados no YPP se forem
  só trechos copiados. Conseguir autorização das fontes, agregar valor (título com contexto,
  comentário, edição própria) e variar as fontes.

### Acompanhamento semanal

| Semana | Shorts postados | Visualizações intencionais/dia | Continuaram (%) | Assistida (%) | Inscritos (total) |
|---|---|---|---|---|---|
| 0 (28/10) | 1 | 592 | 56,2 | 65,2 | 1 |

---

## Próximas evoluções (por impacto)

### ✅ Abertura com teaser (feito em 2026-10-29)

O short começa com 1,2 a 3,5s do momento mais forte da 2ª metade do trecho (exclamação,
número, frase conclusiva), com zoom de 8% para marcar a prévia, e depois volta ao início.
`backend/app/pipeline/teaser.py`; JSON `teaser: {enabled, clips, text}`; `render_clips()` =
teaser + corte. Liga e desliga com `TEASER_ENABLED`, no PATCH `teaser`, no PC e no app. O alvo
de duração desconta o teaser. **Medir:** "continuaram assistindo" dos cortes com teaser
contra os 56,2% de 28/10.

### 0. Gancho do primeiro segundo (ligado à meta: continuaram assistindo de 56% para ≥ 65%)

**Onde:** `backend/app/pipeline/select.py` (peso do `hook`) e `captions.py` (título na tela).
- Dar mais peso à primeira frase: pergunta, número, afirmação forte, nome conhecido.
- Começar o corte exatamente na primeira palavra (sem respiro antes).
- Título na tela curto (até ~6 palavras) e em destaque já no frame 0.
- Validar comparando "continuaram assistindo" dos cortes antes e depois.

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
