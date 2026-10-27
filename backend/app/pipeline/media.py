"""Utilitários de ffmpeg/ffprobe: metadados, silêncios e energia do áudio."""
import json
import re
import subprocess
from pathlib import Path

import numpy as np


class FFmpegError(RuntimeError):
    pass


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise FFmpegError(f"{cmd[0]} falhou ({proc.returncode}):\n{proc.stderr[-2000:]}")
    return proc


def probe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "quiet", "-print_format", "json",
               "-show_format", "-show_streams", str(path)]).stdout
    info = json.loads(out)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if video is None:
        raise ValueError("arquivo sem trilha de vídeo")
    if audio is None:
        raise ValueError("arquivo sem trilha de áudio")

    width, height = int(video["width"]), int(video["height"])
    # Vídeos de celular costumam vir com rotação nos metadados
    rotation = 0
    for sd in video.get("side_data_list", []):
        if "rotation" in sd:
            rotation = abs(int(sd["rotation"])) % 360
    if rotation in (90, 270):
        width, height = height, width

    num, den = video.get("avg_frame_rate", "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    return {
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "duration": float(info["format"]["duration"]),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
    }


def extract_audio(src: Path, dst: Path) -> Path:
    """WAV mono 16 kHz: formato que o Whisper usa e rápido de analisar."""
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(dst)])
    return dst


def detect_silences(wav: Path, noise_db: float = -35, min_dur: float = 0.3) -> list[dict]:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(wav), "-af",
         f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    silences, start = [], None
    for line in proc.stderr.splitlines():
        if m := re.search(r"silence_start: ([\d.]+)", line):
            start = float(m.group(1))
        elif (m := re.search(r"silence_end: ([\d.]+)", line)) and start is not None:
            silences.append({"start": round(start, 3), "end": round(float(m.group(1)), 3)})
            start = None
    return silences


def audio_energy(wav: Path, window_s: float = 0.5) -> list[float]:
    """RMS em dBFS por janela; usado para pontuar trechos mais 'animados'."""
    import wave

    with wave.open(str(wav), "rb") as w:
        rate = w.getframerate()
        samples = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    samples /= 32768.0
    hop = int(rate * window_s)
    n = len(samples) // hop
    if n == 0:
        return []
    frames = samples[: n * hop].reshape(n, hop)
    rms = np.sqrt((frames ** 2).mean(axis=1)) + 1e-9
    return [round(float(v), 2) for v in 20 * np.log10(rms)]
