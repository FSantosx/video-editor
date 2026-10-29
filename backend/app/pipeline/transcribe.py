"""Transcrição com timestamps por palavra.

Saída padronizada (independente do motor):
    [{"word": "Olá", "start": 0.52, "end": 0.80, "prob": 0.98}, ...]
"""
import json
import logging
import os
import sys
import threading
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np

from .. import config


log = logging.getLogger("transcribe")


def _add_cuda_dll_dirs() -> None:
    """Windows: as DLLs do cuBLAS/cuDNN vêm dos pacotes pip nvidia-*; o
    CTranslate2 só as encontra se as pastas estiverem no caminho de busca."""
    if sys.platform != "win32":
        return
    try:
        import nvidia
    except ImportError:
        return
    for base in nvidia.__path__:
        for bin_dir in Path(base).glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


_model_lock = threading.Lock()


@lru_cache(maxsize=1)
def _whisper_model():
    with _model_lock:  # pré-carga do modo desktop e uma análise podem chegar juntas
        return _load_model()


def _load_model():
    from faster_whisper import WhisperModel

    device = config.WHISPER_DEVICE
    if device in ("cuda", "auto"):
        _add_cuda_dll_dirs()
        try:
            compute = config.WHISPER_COMPUTE if config.WHISPER_COMPUTE != "int8" else "float16"
            model = WhisperModel(config.WHISPER_MODEL, device="cuda", compute_type=compute)
            log.info("Whisper %s na GPU (%s)", config.WHISPER_MODEL, compute)
            return model
        except Exception as exc:  # sem placa, driver ou DLLs: segue na CPU
            if device == "cuda":
                log.warning("GPU indisponível (%s); usando CPU", exc)
    log.info("Whisper %s na CPU (int8)", config.WHISPER_MODEL)
    return WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")


def describe_device() -> str:
    """'cuda' ou 'cpu', conforme o modelo realmente carregado (para a interface)."""
    return getattr(_whisper_model().model, "device", "cpu")


def load_wav(wav: Path) -> np.ndarray:
    """Lê o WAV 16 kHz mono (gerado pelo ffmpeg) como float32 em [-1, 1].

    Passar o array evita que o faster-whisper abra o arquivo com PyAV: o
    faster-whisper 1.2.1 chama av.open(metadata_errors=...), parâmetro que o
    PyAV removeu, o que quebrava a transcrição.
    """
    with wave.open(str(wav), "rb") as w:
        if w.getframerate() != 16000 or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("WAV precisa ser 16 kHz, mono, 16 bits")
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0


def transcribe(wav: Path, source: Path, on_progress=None) -> tuple[list[dict], str | None]:
    if config.TRANSCRIBER == "sidecar":
        return _sidecar(source), config.WHISPER_LANGUAGE

    segments, info = _whisper_model().transcribe(
        load_wav(wav),
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
                # float(): o faster-whisper pode devolver numpy.float64, e comparações
                # com ele viram numpy.bool_, que não vai para o JSON
                words.append({"word": text, "start": round(float(w.start), 3),
                              "end": round(float(w.end), 3),
                              "prob": round(float(w.probability), 3)})
        if on_progress and info.duration:
            on_progress(min(seg.end / info.duration, 1.0))
    return words, info.language


def _sidecar(source: Path) -> list[dict]:
    """Lê palavras pré-calculadas de SIDECAR_WORDS ou <video>.words.json (testes sem modelo)."""
    path = Path(os.getenv("SIDECAR_WORDS") or source.with_suffix(".words.json"))
    if not path.exists():
        raise FileNotFoundError(f"TRANSCRIBER=sidecar mas {path.name} não existe")
    return json.loads(path.read_text(encoding="utf-8"))
