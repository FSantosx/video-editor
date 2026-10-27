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
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "pt") or None
# "whisper" (produção) ou "sidecar" (lê <video>.words.json; usado nos testes locais)
TRANSCRIBER = os.getenv("TRANSCRIBER", "whisper")

# Regras dos shorts
SHORT_MIN_S = _env_float("SHORT_MIN_S", 30)
SHORT_MAX_S = _env_float("SHORT_MAX_S", 60)
MAX_SHORTS = _env_int("MAX_SHORTS", 5)
PAUSE_CUT_S = _env_float("PAUSE_CUT_S", 0.35)  # pausas maiores que isso viram corte seco

# Render
OUT_W, OUT_H, OUT_FPS = 1080, 1920, 30
X264_PRESET = os.getenv("X264_PRESET", "veryfast")
X264_CRF = os.getenv("X264_CRF", "21")
CAPTION_FONT = os.getenv("CAPTION_FONT", "DejaVu Sans")
