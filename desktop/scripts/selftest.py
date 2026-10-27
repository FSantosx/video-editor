"""Autoteste do Video Editor no PC: roda no fim da instalação.

Confere ffmpeg (legendas e NVENC), carrega o modelo do Whisper (baixa na 1ª vez),
transcreve um áudio curto (exercita cuBLAS/cuDNN na GPU) e renderiza um vídeo
de 2s com legenda usando o encoder configurado.

Códigos de saída: 0 = ok, 2 = falha tratada. Qualquer outro código significa que
o processo abortou (tipicamente DLL do CUDA incompatível) e o instalador passa
a usar a CPU.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

import numpy as np  # noqa: E402

from app import config  # noqa: E402
from app.pipeline import captions, render, transcribe  # noqa: E402


def check(label: str, fn):
    t0 = time.time()
    try:
        detail = fn()
    except Exception as exc:  # mostra o erro e marca falha
        print(f"    XX  {label}: {exc}", flush=True)
        return False
    print(f"    OK  {label}: {detail} ({time.time() - t0:.1f}s)", flush=True)
    return True


def ffmpeg_ok():
    filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace").stdout
    if " subtitles " not in filters:
        raise RuntimeError("ffmpeg sem libass (filtro subtitles)")
    return "legendas disponíveis"


def encoder_ok():
    enc = render.video_encoder()
    return "NVENC (GPU)" if enc == "h264_nvenc" else "x264 (CPU)"


def whisper_ok():
    model = transcribe._whisper_model()
    device = transcribe.describe_device()
    # 4s de ruído baixo, sem VAD: força o modelo a rodar de verdade (cuDNN na GPU)
    audio = (np.random.default_rng(0).standard_normal(16000 * 4) * 0.01).astype(np.float32)
    segments, _ = model.transcribe(audio, language=config.WHISPER_LANGUAGE, vad_filter=False,
                                   beam_size=1)
    list(segments)
    if config.WHISPER_DEVICE in ("cuda", "auto") and device != "cuda":
        print("    !!  GPU não disponível para o Whisper: usando CPU", flush=True)
    return f"{config.WHISPER_MODEL} na {'GPU' if device == 'cuda' else 'CPU'}"


def render_ok():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = tmp / "fonte.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1280x720:d=3",
                        "-f", "lavfi", "-i", "sine=f=300:d=3", "-shortest", "-c:v", "libx264",
                        "-preset", "ultrafast", "-c:a", "aac", str(src)], check=True)
        words = [{"word": "Teste", "start": 0.2, "end": 0.8}, {"word": "legenda.", "start": 0.9, "end": 1.6}]
        short = {"id": 1, "format": config.FORMATS[0], "title": "Autoteste", "clips": [{"in": 0.0, "out": 2.0}],
                 "duration": 2.0, "reframe": {"mode": "crop", "centers": [0.5]},
                 "captions": {"enabled": True}, "title_overlay": {"enabled": True, "seconds": 1.0}}
        meta = {"width": 1280, "height": 720}
        out = render.render_short(src, short, meta, words, tmp / "out")
        size = (tmp / "out" / out["file"]).stat().st_size
        if size < 10_000:
            raise RuntimeError("vídeo gerado vazio")
        return f"{config.FORMATS[0]} com legenda ({size // 1024} KB, {render.video_encoder()})"


def main() -> int:
    print(f"    Formatos: {', '.join(config.FORMATS)} | dados: {config.DATA_DIR}", flush=True)
    results = [
        check("ffmpeg", ffmpeg_ok),
        check("encoder de vídeo", encoder_ok),
        check("transcrição", whisper_ok),
        check("render", render_ok),
    ]
    return 0 if all(results) else 2


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    sys.exit(main())
