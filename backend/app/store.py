"""Armazenamento em disco (um diretório por vídeo, no volume do Railway).

data/videos/<id>/
    source.mp4        upload original
    video.json        status, progresso, metadados
    analysis.json     palavras, silêncios, energia (cache: só calcula uma vez)
    shorts.json       lista de JSONs de edição
    shorts/           short_<n>.mp4 / .jpg / .ass
"""
import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path

from . import config

_lock = threading.RLock()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def video_dir(vid: str) -> Path:
    if not vid.isalnum():
        raise KeyError(vid)
    return config.VIDEOS_DIR / vid


def _read(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def _write(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    os.replace(tmp, path)  # atômico: nunca deixa JSON pela metade


def create_video(filename: str) -> dict:
    vid = new_id()
    d = video_dir(vid)
    (d / "shorts").mkdir(parents=True)
    video = {"id": vid, "filename": filename, "created_at": time.time(),
             "status": "uploading", "step": None, "progress": 0.0, "error": None,
             "meta": None, "language": None}
    _write(d / "video.json", video)
    _write(d / "shorts.json", [])
    return video


def get_video(vid: str) -> dict:
    video = _read(video_dir(vid) / "video.json")
    if video is None:
        raise KeyError(vid)
    return video


def update_video(vid: str, **fields) -> dict:
    with _lock:
        video = get_video(vid)
        video.update(fields)
        _write(video_dir(vid) / "video.json", video)
        return video


def list_videos() -> list[dict]:
    if not config.VIDEOS_DIR.exists():
        return []
    videos = [v for d in config.VIDEOS_DIR.iterdir() if (v := _read(d / "video.json"))]
    return sorted(videos, key=lambda v: v["created_at"], reverse=True)


def delete_video(vid: str) -> None:
    shutil.rmtree(video_dir(vid), ignore_errors=True)


def source_path(vid: str) -> Path:
    d = video_dir(vid)
    found = next(d.glob("source.*"), None)
    if found is None:
        raise KeyError(vid)
    return found


def get_analysis(vid: str) -> dict | None:
    return _read(video_dir(vid) / "analysis.json")


def save_analysis(vid: str, analysis: dict) -> None:
    _write(video_dir(vid) / "analysis.json", analysis)


def get_shorts(vid: str) -> list[dict]:
    return _read(video_dir(vid) / "shorts.json", [])


def save_shorts(vid: str, shorts: list[dict]) -> None:
    with _lock:
        _write(video_dir(vid) / "shorts.json", shorts)


def get_short(vid: str, sid: int) -> dict:
    for s in get_shorts(vid):
        if s["id"] == sid:
            return s
    raise KeyError(sid)


def update_short(vid: str, sid: int, mutate) -> dict:
    """Aplica mutate(short) sob lock e salva. Retorna o short atualizado."""
    with _lock:
        shorts = get_shorts(vid)
        for s in shorts:
            if s["id"] == sid:
                mutate(s)
                save_shorts(vid, shorts)
                return s
    raise KeyError(sid)
