"""Caminho TRANSCRIBER=whisper com um modelo falso (o modelo real não é baixado nos testes)."""
import subprocess
from types import SimpleNamespace

import numpy as np

from app import config
from app.pipeline import media, transcribe


class FakeModel:
    def __init__(self):
        self.audio = None

    def transcribe(self, audio, **kwargs):
        self.audio = audio
        words = [SimpleNamespace(word=" Olá", start=0.1, end=0.4, probability=0.9),
                 SimpleNamespace(word=" mundo.", start=0.5, end=0.9, probability=0.8)]
        segments = iter([SimpleNamespace(words=words, end=0.9)])
        return segments, SimpleNamespace(duration=1.0, language="pt")


def test_whisper_receives_numpy_array_not_path(tmp_path, monkeypatch):
    video = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=f=300:d=2",
                    "-f", "lavfi", "-i", "color=s=64x64:d=2", "-shortest", str(video)], check=True)
    wav = media.extract_audio(video, tmp_path / "a.wav")

    fake = FakeModel()
    monkeypatch.setattr(config, "TRANSCRIBER", "whisper")
    monkeypatch.setattr(transcribe, "_whisper_model", lambda: fake)
    progress = []
    words, lang = transcribe.transcribe(wav, video, progress.append)

    # Array float32 16 kHz: o faster-whisper não abre o arquivo com PyAV
    assert isinstance(fake.audio, np.ndarray) and fake.audio.dtype == np.float32
    assert abs(len(fake.audio) / 16000 - 2.0) < 0.1
    assert np.abs(fake.audio).max() <= 1.0
    assert [w["word"] for w in words] == ["Olá", "mundo."]
    assert lang == "pt" and progress[-1] == 0.9
