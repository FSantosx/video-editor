# Video Editor: shorts automáticos

Envie um vídeo longo pelo app Android e receba shorts verticais (9:16) de 30 a 60 segundos,
já cortados, com legendas animadas e o rosto de quem fala enquadrado.

```
App Flutter (Android)  ──upload──►  API FastAPI (Railway)
        ▲                               │ 1. transcrição (faster-whisper, timestamps por palavra)
        │                               │ 2. seleção dos melhores trechos (heurística)
        │                               │ 3. corte de pausas, hesitações e frases de bastidor
        │                               │ 4. reenquadramento 9:16 seguindo o rosto (OpenCV)
        │                               │ 5. legendas .ass estilo TikTok + título
        └──── JSON de edição + MP4 ◄────┘ 6. render com ffmpeg (uma única codificação)
```

O coração do sistema é o **JSON de edição** de cada short: o vídeo original nunca é alterado,
o app edita o JSON (título, início/fim, legendas, enquadramento) e o servidor renderiza de novo.

```json
{
  "id": 1, "title": "Você sabia que o maior erro…", "score": 87,
  "window": {"start": 28.9, "end": 88.1},
  "clips": [{"in": 28.84, "out": 33.08}, {"in": 33.42, "out": 35.48}, "..."],
  "duration": 44.8,
  "reframe": {"mode": "crop", "centers": [0.26, 0.26, 0.73]},
  "captions": {"enabled": true},
  "title_overlay": {"enabled": true, "seconds": 3.0},
  "render": {"status": "done", "version": 1, "file": "short_1.mp4"}
}
```

| Pasta | O que tem |
|---|---|
| `backend/` | API FastAPI, pipeline de vídeo, Dockerfile e `railway.json` |
| `mobile/` | App Flutter (Android, com iOS de brinde) |
| `.github/workflows/` | Testes do backend e build do APK a cada push |

---

## Backend

### Rodar localmente

Requer Python 3.12+ e `ffmpeg` instalado.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
API_KEY=minha-chave uvicorn app.main:app --reload --port 8000
```

Na primeira análise, o faster-whisper baixa o modelo (`base`, cerca de 150 MB) do HuggingFace.

Para testar sem modelo nenhum, use o vídeo sintético com fala em português (requer `espeak-ng`):

```bash
python tools/make_test_video.py /tmp/teste.mp4   # gera /tmp/teste.mp4 e /tmp/teste.words.json
TRANSCRIBER=sidecar SIDECAR_WORDS=/tmp/teste.words.json uvicorn app.main:app --port 8000
curl -H "X-API-Key: minha-chave" -F file=@/tmp/teste.mp4 localhost:8000/videos
```

Testes: `python -m pytest -q`

### Deploy no Railway

1. **New Project → Deploy from GitHub repo** e escolha este repositório.
2. Em **Settings → Source**, defina **Root Directory** = `backend`. O Railway usa o `Dockerfile`
   e o `railway.json` dessa pasta.
3. Em **Variables**, defina:
   - `API_KEY`: uma senha longa, que você também coloca no app. **Obrigatória**, senão a API fica aberta.
   - Opcionais: `WHISPER_MODEL` (`base` por padrão; `small` transcreve melhor e é cerca de 3x mais lento),
     `MAX_SHORTS` (5), `SHORT_MIN_S` (30), `SHORT_MAX_S` (60), `WORKERS` (1).
4. Clique com o botão direito no serviço → **Attach Volume**, com mount path `/data`.
   Sem volume, os vídeos somem a cada deploy.
5. Em **Settings → Networking → Generate Domain**, gere a URL `https://<algo>.up.railway.app`,
   que vai no app.

Se mudar `WHISPER_MODEL`, o modelo também precisa ser trocado no build. Para isso, crie a variável
de build com o mesmo nome; o Railway a repassa como `ARG` do Dockerfile.

**Desempenho esperado (CPU, sem GPU):** a transcrição domina o tempo. Com o modelo `base` em int8,
ela roda bem mais rápido que o tempo real do vídeo. Cada short de cerca de 45s levou de 25 a 40s
para reenquadrar e renderizar num container de 4 vCPUs.

### API

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/videos` | Upload (multipart `file`). Analisa e renderiza os shorts sozinho. |
| `GET` | `/videos` | Lista vídeos com os shorts. |
| `GET` | `/videos/{id}` | Status, progresso (`step`, `progress`) e JSON dos shorts. |
| `DELETE` | `/videos/{id}` | Apaga tudo. |
| `GET` | `/videos/{id}/transcript` | Palavras com timestamps. |
| `POST` | `/videos/{id}/reanalyze` | Refaz a seleção sem transcrever de novo. |
| `PATCH` | `/videos/{id}/shorts/{n}` | `title`, `start`, `end`, `captions`, `title_overlay`, `crop_center`, `auto_reframe`. Dispara o re-render. |
| `GET` | `/videos/{id}/shorts/{n}/video` | MP4 (aceita `Range`). |
| `GET` | `/videos/{id}/shorts/{n}/thumb` | Miniatura JPG. |

Autenticação: header `X-API-Key` (ou `?key=`).

---

## App Android

### Baixar o APK pronto

Cada push em `mobile/` roda o workflow **mobile** no GitHub Actions, que testa e gera o APK.
Abra **Actions → mobile → (última execução) → Artifacts → shorts-editor-apk**, baixe e instale
no celular (permita "instalar apps desconhecidos").

No primeiro uso, informe a URL do Railway e a `API_KEY`.

### Gerar o APK no GitHub Codespaces

O repositório tem um `.devcontainer` que instala Flutter 3.47.8 e o Android SDK.

1. No GitHub: **Code → Codespaces → ⋯ → New with options**, escolha a máquina de
   **4 núcleos / 16 GB** e clique em **Create codespace**. A primeira criação leva de 5 a 10 minutos,
   porque instala os SDKs; acompanhe pelo terminal ou em *View creation log*.
2. Quando o terminal mostrar "Pronto!", rode:
   ```bash
   cd mobile
   flutter build apk --release
   ```
3. No Explorer, abra `mobile/build/app/outputs/flutter-apk/`, clique com o botão direito em
   `app-release.apk` e escolha **Download**.

Pare o codespace ao terminar (**Codespaces → Stop**), porque ele consome a cota gratuita enquanto
estiver ligado. O emulador Android não roda no Codespaces: teste instalando o APK no celular.

### Desenvolver localmente

Requer Flutter 3.47+ e Android SDK.

```bash
cd mobile
flutter pub get
flutter run                 # com o celular plugado ou um emulador
flutter test && flutter analyze
flutter build apk --release
```

No build de **debug**, o app aceita `http://` para testar com o servidor local
(`http://IP-do-computador:8000`). No de release, só `https://`.

Para publicar na Play Store, crie uma chave de release e configure `signingConfigs` em
`android/app/build.gradle.kts`. Hoje o release é assinado com a chave de debug.

---

## Limitações conhecidas e próximos passos

O plano detalhado de evolução, com as decisões já tomadas, está em **[ROADMAP.md](ROADMAP.md)**.

- **Seleção por heurística:** usa ritmo de fala, energia do áudio, palavras de gancho e frases
  completas, e corta frases de bastidor ("bom, deixa eu ajustar a câmera"). Funciona, mas não
  entende o conteúdo. O próximo passo é um seletor com LLM, que é só trocar a função
  `select_shorts` em `backend/app/pipeline/select.py`, já que ela tem a mesma interface.
- **Detecção de rosto Haar (OpenCV 4):** é leve e não baixa modelos, mas falha com rosto de
  perfil ou muito pequeno. Quando não há rosto, o vídeo inteiro vai centralizado sobre fundo
  desfocado. Alternativas melhores: MediaPipe ou YuNet.
- **Fila de jobs em memória:** suficiente para um container. Os jobs pendentes são retomados após
  restart, mas para vários servidores seria preciso Redis/RQ ou Celery.
- **Armazenamento:** os vídeos ficam no volume até você apagá-los pelo app. Não há limpeza automática.
