# Video Editor no PC (Windows)

Roda tudo localmente, com a interface no navegador. Usa a placa NVIDIA para transcrever
(Whisper `large-v3-turbo`) e para codificar os vídeos (NVENC). Para cada trecho escolhido, gera
cortes em **9:16** (Shorts/Reels/TikTok) e **1:1** (feed).

Feito e testado pensando em: Ryzen 7 5800X3D · RTX 3070 (8 GB) · 16 GB de RAM · Windows 10/11.

## Instalação (uma vez)

1. **Driver da NVIDIA atualizado** (GeForce Experience ou nvidia.com). Não precisa instalar o
   CUDA Toolkit: as bibliotecas necessárias vêm junto.
2. Baixe o repositório:
   - com Git: `git clone https://github.com/FSantosx/video-editor.git`
   - ou **Code → Download ZIP** no GitHub e extraia, de preferência num caminho curto como `C:\video-editor`.
3. Abra a pasta `desktop` e dê dois cliques em **`Instalar.bat`**. Ele:
   - instala o Python 3.12 (via winget), se não houver;
   - cria o ambiente com as dependências e as bibliotecas CUDA (cuBLAS e cuDNN);
   - baixa o ffmpeg com NVENC e suporte a legendas;
   - baixa o modelo do Whisper (cerca de 1,6 GB) e roda um **autoteste** de GPU, NVENC e legendas;
   - cria o atalho **Video Editor** na Área de Trabalho.

   Se a GPU falhar no autoteste, ele configura a CPU automaticamente e avisa.

Leva de 5 a 15 minutos, conforme a internet. Precisa de uns 6 GB livres.

## Uso

1. Dê dois cliques em **Video Editor** (ou `Iniciar.bat`). Abre uma janela preta (o servidor) e o
   navegador em **http://localhost:8765**.
2. Arraste um ou mais vídeos para a área da esquerda. Eles entram numa fila.
3. Acompanhe: transcrição → escolha dos trechos → render. Cada trecho aparece com as duas versões
   (9:16 e 1:1).
4. **Editar** abre os players lado a lado: título, início e fim, legendas, título na tela e
   enquadramento. Com "Aplicar a todos os formatos" marcado, a mudança vale para o 9:16 e o 1:1 juntos.
5. **Baixar** salva o MP4, e **📂 Abrir pasta dos cortes** abre a pasta no Explorer.

Para parar, feche a janela preta. Nada sai do seu PC: tudo roda em `127.0.0.1`.

### Desempenho esperado na RTX 3070

- A transcrição com `large-v3-turbo` na GPU fica muito acima do tempo real: um vídeo de 1 hora
  deve levar poucos minutos. Na primeira vez há alguns segundos extras para carregar o modelo.
- O render de cada corte com NVENC leva segundos, com dois cortes ao mesmo tempo (`WORKERS=2`).
- A etapa mais lenta por corte costuma ser a detecção de rosto, que roda na CPU e se beneficia
  dos 8 núcleos do 5800X3D.

## Configuração

Edite `desktop\config.env` (criado na instalação) e reinicie:

| Chave | Padrão | Para quê |
|---|---|---|
| `WHISPER_MODEL` | `large-v3-turbo` | `large-v3` transcreve um pouco melhor e é bem mais lento; `small` é para a CPU |
| `WHISPER_DEVICE` | `auto` | `cpu` força a CPU |
| `FORMATS` | `9:16,1:1` | só `9:16` ou só `1:1`, se preferir |
| `MAX_SHORTS` | `8` | quantos trechos escolher por vídeo |
| `SHORT_MIN_S` / `SHORT_MAX_S` | `30` / `60` | duração dos cortes, em segundos |
| `VIDEO_ENCODER` | `auto` | `libx264` força a CPU |
| `NVENC_CQ` | `21` | qualidade: menor é melhor e gera arquivo maior (18 a 24) |
| `WORKERS` | `2` | cortes renderizados ao mesmo tempo |
| `DATA_DIR` | `desktop\data` | onde ficam vídeos e cortes, ex.: `D:\Cortes` |
| `PORT` | `8765` | porta da interface |

## Atualizar

- **Com Git:** `Atualizar.bat` baixa a versão nova e atualiza as dependências.
- **Com ZIP:** baixe o ZIP novo, extraia por cima (o `config.env` e a pasta `data` são preservados)
  e rode o `Instalar.bat`.

## Problemas comuns

| Sintoma | Solução |
|---|---|
| Chip "CPU" no topo da interface | Atualize o driver da NVIDIA e rode o `Instalar.bat` de novo; veja o autoteste |
| "x264 (CPU)" em vez de NVENC | Driver antigo: atualize. O render funciona na CPU, só mais devagar |
| `Instalar.bat` fecha ou diz que o Python não foi encontrado | Instale o Python 3.12 em python.org (marque "Add to PATH") e rode de novo |
| A porta 8765 está ocupada | Mude `PORT` no `config.env` |
| Legenda com fonte diferente | Mude `CAPTION_FONT` (ex.: `Arial Black`, `Segoe UI`) |
| Quero apagar tudo | Feche o servidor e apague a pasta. O modelo fica em `desktop\models` |

## Como funciona

A pasta `desktop` não duplica código: ela roda o mesmo backend de `backend/` (o do Railway),
em modo desktop (`DESKTOP_MODE=1`), com GPU e com a interface de `desktop/web/`. Qualquer melhoria
no pipeline vale para o PC, o servidor e o app ao mesmo tempo.

```
desktop/
  Instalar.bat / Iniciar.bat / Atualizar.bat   atalhos (chamam os scripts PowerShell)
  config.example.env                           configurações padrão
  scripts/install.ps1, start.ps1, common.ps1   instalação e inicialização
  scripts/selftest.py                          autoteste (GPU, NVENC, legendas)
  web/                                         interface (HTML/CSS/JS, sem build)
```

O workflow `.github/workflows/desktop.yml` roda a instalação e um teste de ponta a ponta num
Windows de verdade a cada mudança (sem GPU, então valida o caminho da CPU).
