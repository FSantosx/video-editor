"""Transcrição com timestamps por palavra.

Saída padronizada (independente do motor):
    [{"word": "Olá", "start": 0.52, "end": 0.80, "prob": 0.98}, ...]
"""
import json
import os
from functools import lru_cache
from pathlib import Path

from .. import config


@lru_cache(maxsize=1)
def _whisper_model():
    from faster_whisper import WhisperModel

    return WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type=config.WHISPER_COMPUTE)


def transcribe(wav: Path, source: Path, on_progress=None) -> tuple[list[dict], str | None]:
    if config.TRANSCRIBER == "sidecar":
        return _sidecar(source), config.WHISPER_LANGUAGE

    segments, info = _whisper_model().transcribe(
        str(wav),
        language=config.WHISPER_LANGUAGE,
        word_timestamps=True,
        vad_filter=True,
        beam_size=1,  # bem mais rápido em CPU, perda de qualidade pequena
    )
    words = []
    for seg in segments:  # gerador: a transcrição acontece enquanto iteramos
        for w in seg.words or []:
            text = w.word.strip()
            if text:
                words.append({"word": text, "start": round(w.start, 3),
                              "end": round(w.end, 3), "prob": round(w.probability, 3)})
        if on_progress and info.duration:
            on_progress(min(seg.end / info.duration, 1.0))
    return words, info.language


def _sidecar(source: Path) -> list[dict]:
    """Lê palavras pré-calculadas de SIDECAR_WORDS ou <video>.words.json (testes sem modelo)."""
    path = Path(os.getenv("SIDECAR_WORDS") or source.with_suffix(".words.json"))
    if not path.exists():
        raise FileNotFoundError(f"TRANSCRIBER=sidecar mas {path.name} não existe")
    return json.loads(path.read_text())
