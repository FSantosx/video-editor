"""Configuração via variáveis de ambiente (Railway injeta PORT e as suas variáveis)."""
import os
from pathlib import Path


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
VIDEOS_DIR = DATA_DIR / "videos"

# Chave simples para proteger a API pública. Vazia = sem autenticação (só para dev).
API_KEY = os.getenv("API_KEY", "")

MAX_UPLOAD_MB = _env_int("MAX_UPLOAD_MB", 2048)
WORKERS = _env_int("WORKERS", 1)  # quantos vídeos processar ao mesmo tempo

# Transcrição (faster-whisper). Railway não tem GPU: CPU + int8.
# No PC com placa NVIDIA: WHISPER_DEVICE=cuda (ou auto), WHISPER_COMPUTE=float16.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")  # cpu | cuda | auto
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "pt") or None
# "whisper" (produção) ou "sidecar" (lê <video>.words.json; usado nos testes locais)
TRANSCRIBER = os.getenv("TRANSCRIBER", "whisper")

# Regras dos shorts
SHORT_MIN_S = _env_float("SHORT_MIN_S", 30)
SHORT_MAX_S = _env_float("SHORT_MAX_S", 60)
# Duração preferida (dentro de MIN/MAX). Feedback do YouTube: com 55s a retenção média
# ficou em 48,8%; cortes mais curtos seguram melhor até o fim.
SHORT_TARGET_S = _env_float("SHORT_TARGET_S", 38)
MAX_SHORTS = _env_int("MAX_SHORTS", 5)
PAUSE_CUT_S = _env_float("PAUSE_CUT_S", 0.25)  # pausas maiores que isso viram corte seco

# Chamada no final do corte (pede comentário: ajuda a completar o vídeo e engajar)
CTA_ENABLED = os.getenv("CTA_ENABLED", "1") == "1"
CTA_TEXT = os.getenv("CTA_TEXT", "E você, o que acha? Comenta aí!")
CTA_SECONDS = _env_float("CTA_SECONDS", 3.0)

# Abertura com teaser: o short começa com o momento mais forte do trecho e depois volta
# ao início (ataca quem desliza nos primeiros segundos)
TEASER_ENABLED = os.getenv("TEASER_ENABLED", "1") == "1"
TEASER_MAX_S = _env_float("TEASER_MAX_S", 3.5)
TEASER_ZOOM = _env_float("TEASER_ZOOM", 1.08)  # leve zoom para marcar que é uma prévia

# Zoom dinâmico: clips do corte alternam entre enquadramento normal e "punch-in"
# (cada jump cut vira uma mudança de enquadramento, o que esconde o pulo e dá ritmo)
ZOOM_ENABLED = os.getenv("ZOOM_ENABLED", "1") == "1"
ZOOM_PUNCH = _env_float("ZOOM_PUNCH", 1.12)
ZOOM_FOCUS_Y = _env_float("ZOOM_FOCUS_Y", 0.4)  # o zoom mira um pouco acima do centro (rosto)

# Final em loop (exige teaser): o corte termina logo antes da frase do teaser; ao recomeçar,
# o teaser soa como a continuação da última frase e a pessoa assiste de novo
LOOP_ENABLED = os.getenv("LOOP_ENABLED", "1") == "1"
LOOP_TEASER_FROM = _env_float("LOOP_TEASER_FROM", 0.55)  # teaser do loop vem do fim do trecho
# o loop não pode deixar o corte abaixo da duração mínima
LOOP_MIN_S = _env_float("LOOP_MIN_S", SHORT_MIN_S)

# Título de gancho (texto na tela) e título do post. auto = Claude se houver
# ANTHROPIC_API_KEY, senão heurística; llm = sempre tenta o Claude; heuristic = nunca usa
TITLES_ENGINE = os.getenv("TITLES_ENGINE", "auto")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
CLAUDE_EFFORT = os.getenv("CLAUDE_EFFORT", "medium")

# Versão do pipeline de edição: aumente quando a forma de gerar os cortes mudar.
# Vídeos processados com versão menor aparecem como "desatualizados" e podem ser
# reprocessados (sem transcrever de novo).
# 1 = MVP · 2 = retenção (38s, final conclusivo, chamada) · 3 = teaser · 4 = gancho
# 5 = zoom dinâmico + final em loop
PIPELINE_VERSION = 5

# Formatos gerados para cada trecho escolhido (largura x altura da saída)
FORMAT_SIZES = {"9:16": (1080, 1920), "1:1": (1080, 1080)}
FORMATS = [f.strip() for f in os.getenv("FORMATS", "9:16").split(",") if f.strip()]
_unknown = set(FORMATS) - set(FORMAT_SIZES)
if _unknown or not FORMATS:
    raise ValueError(f"FORMATS inválido: {_unknown or 'vazio'}; opções: {', '.join(FORMAT_SIZES)}")

# Render
OUT_FPS = 30
# libx264 (CPU) | h264_nvenc (placa NVIDIA) | auto (usa NVENC se o ffmpeg e a placa suportarem)
VIDEO_ENCODER = os.getenv("VIDEO_ENCODER", "libx264")
X264_PRESET = os.getenv("X264_PRESET", "veryfast")
X264_CRF = os.getenv("X264_CRF", "21")
NVENC_PRESET = os.getenv("NVENC_PRESET", "p5")
NVENC_CQ = os.getenv("NVENC_CQ", "21")
CAPTION_FONT = os.getenv("CAPTION_FONT", "DejaVu Sans")

# Modo desktop (PC local): serve a interface web e libera ações locais (abrir pasta)
DESKTOP_MODE = os.getenv("DESKTOP_MODE", "") == "1"
WEB_DIR = Path(os.getenv("WEB_DIR", Path(__file__).resolve().parents[2] / "desktop" / "web"))
