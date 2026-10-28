"""API HTTP consumida pelo app Android.

Fluxo:
  POST  /videos                         upload -> análise -> shorts renderizados sozinhos
  GET   /videos/{id}                    status/progresso + lista de shorts (JSON de edição)
  PATCH /videos/{id}/shorts/{n}         edita título/início/fim/legendas -> re-render
  GET   /videos/{id}/shorts/{n}/video   MP4 final (aceita Range, dá para tocar em streaming)
"""
import logging
import os
import secrets
import shutil
import subprocess
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, jobs, store
from .pipeline import render, transcribe
from .pipeline.edit import apply_window

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
ALLOWED_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    jobs.resume_pending()
    if config.DESKTOP_MODE and config.TRANSCRIBER == "whisper":
        # Carrega o modelo em segundo plano: a 1ª análise não espera e a interface já
        # mostra se ficou na GPU ou na CPU
        threading.Thread(target=transcribe._whisper_model, daemon=True).start()
    yield


app = FastAPI(title="Video Editor - Shorts", version="0.1.0", lifespan=lifespan)


def require_key(request: Request) -> None:
    if not config.API_KEY:
        return
    key = request.headers.get("x-api-key") or request.query_params.get("key") or ""
    if not secrets.compare_digest(key, config.API_KEY):
        raise HTTPException(401, "API key inválida")


def _video_or_404(vid: str) -> dict:
    try:
        return store.get_video(vid)
    except KeyError:
        raise HTTPException(404, "vídeo não encontrado")


def _short_or_404(vid: str, sid: int) -> dict:
    _video_or_404(vid)
    try:
        return store.get_short(vid, sid)
    except KeyError:
        raise HTTPException(404, "short não encontrado")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/videos", dependencies=[Depends(require_key)])
def list_videos():
    return [{**v, "shorts": store.get_shorts(v["id"])} for v in store.list_videos()]


@app.post("/videos", status_code=201, dependencies=[Depends(require_key)])
def upload_video(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower() or ".mp4"
    if ext not in ALLOWED_EXT:
        raise HTTPException(415, f"formato não suportado: {ext}")

    video = store.create_video(file.filename or f"video{ext}")
    dest = store.video_dir(video["id"]) / f"source{ext}"
    limit, written = config.MAX_UPLOAD_MB * 1024 * 1024, 0
    try:
        with dest.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):
                written += len(chunk)
                if written > limit:
                    raise HTTPException(413, f"arquivo maior que {config.MAX_UPLOAD_MB} MB")
                out.write(chunk)
    except BaseException:
        store.delete_video(video["id"])
        raise
    store.update_video(video["id"], size_bytes=written)
    jobs.submit_analysis(video["id"])
    return store.get_video(video["id"])


@app.get("/videos/{vid}", dependencies=[Depends(require_key)])
def get_video(vid: str):
    return {**_video_or_404(vid), "shorts": store.get_shorts(vid)}


@app.delete("/videos/{vid}", status_code=204, dependencies=[Depends(require_key)])
def delete_video(vid: str):
    _video_or_404(vid)
    store.delete_video(vid)


@app.get("/videos/{vid}/transcript", dependencies=[Depends(require_key)])
def get_transcript(vid: str):
    _video_or_404(vid)
    analysis = store.get_analysis(vid)
    if analysis is None:
        raise HTTPException(409, "transcrição ainda não terminou")
    return {"language": analysis.get("language"), "words": analysis["words"]}


@app.post("/videos/{vid}/reanalyze", dependencies=[Depends(require_key)])
def reanalyze(vid: str):
    """Refaz a seleção (sem transcrever de novo). Útil após mudar as regras."""
    _video_or_404(vid)
    jobs.submit_analysis(vid)
    return store.get_video(vid)


class ShortPatch(BaseModel):
    title: str | None = Field(None, max_length=120)
    start: float | None = Field(None, ge=0)
    end: float | None = Field(None, gt=0)
    captions: bool | None = None
    title_overlay: bool | None = None
    # centro horizontal do recorte (0-1) para todos os clips; null volta ao automático
    crop_center: float | None = Field(None, ge=0, le=1)
    auto_reframe: bool | None = None
    # chamada no final do corte (ex.: "E você, o que acha? Comenta aí!")
    cta: bool | None = None
    cta_text: str | None = Field(None, max_length=80)
    # aplica também aos outros formatos do mesmo trecho (ex.: o 1:1 do mesmo 9:16)
    sync_group: bool = False


@app.patch("/videos/{vid}/shorts/{sid}", dependencies=[Depends(require_key)])
def patch_short(vid: str, sid: int, patch: ShortPatch):
    short = _short_or_404(vid, sid)
    meta = store.get_video(vid)["meta"]
    words = store.get_analysis(vid)["words"]

    start = patch.start if patch.start is not None else short["window"]["start"]
    end = patch.end if patch.end is not None else short["window"]["end"]
    if end <= start:
        raise HTTPException(422, "end precisa ser maior que start")
    if end - start > 180:
        raise HTTPException(422, "trecho máximo de 180s")
    if end > meta["duration"] + 0.5:
        raise HTTPException(422, "end além do fim do vídeo")

    def mutate(s):
        if patch.start is not None or patch.end is not None:
            apply_window(s, words, start, end)
            if not s["clips"]:
                raise HTTPException(422, "não há fala nesse intervalo")
        if patch.title is not None:
            s["title"] = patch.title.strip()
        if patch.captions is not None:
            s["captions"]["enabled"] = patch.captions
        if patch.title_overlay is not None:
            s["title_overlay"]["enabled"] = patch.title_overlay
        if patch.cta is not None or patch.cta_text is not None:
            cta = s.setdefault("cta", {"enabled": config.CTA_ENABLED, "text": config.CTA_TEXT})
            if patch.cta is not None:
                cta["enabled"] = patch.cta
            if patch.cta_text is not None and patch.cta_text.strip():
                cta["text"] = patch.cta_text.strip()
        target_w, target_h = config.FORMAT_SIZES[s.get("format", "9:16")]
        if patch.auto_reframe:
            s["reframe"] = {"mode": "auto", "centers": []}
        elif (patch.crop_center is not None
              and meta["width"] / meta["height"] > target_w / target_h):
            s["reframe"] = {"mode": "crop", "centers": [patch.crop_center] * len(s["clips"]),
                            "manual": True}
        s["render"]["status"] = "pending"

    targets = [sid]
    if patch.sync_group:
        group = short.get("group", sid)
        targets += [s["id"] for s in store.get_shorts(vid)
                    if s.get("group", s["id"]) == group and s["id"] != sid]
    for target in targets:
        store.update_short(vid, target, mutate)
    for target in targets:
        jobs.submit_render(vid, target)
    return store.get_short(vid, sid)


@app.post("/videos/{vid}/shorts/{sid}/render", dependencies=[Depends(require_key)])
def rerender(vid: str, sid: int):
    _short_or_404(vid, sid)
    jobs.submit_render(vid, sid)
    return store.get_short(vid, sid)


def _short_file(vid: str, sid: int, key: str, media_type: str) -> FileResponse:
    short = _short_or_404(vid, sid)
    name = short["render"].get(key)
    path = store.video_dir(vid) / "shorts" / name if name else None
    if path is None or not path.exists():
        raise HTTPException(404, "ainda não renderizado")
    filename = None
    if key == "file":  # ex.: corte_2_9x16.mp4
        filename = f"corte_{short.get('group', sid)}_{short.get('format', '9:16').replace(':', 'x')}.mp4"
    return FileResponse(path, media_type=media_type, filename=filename)


@app.get("/videos/{vid}/shorts/{sid}/video", dependencies=[Depends(require_key)])
def short_video(vid: str, sid: int):
    return _short_file(vid, sid, "file", "video/mp4")


@app.get("/videos/{vid}/shorts/{sid}/thumb", dependencies=[Depends(require_key)])
def short_thumb(vid: str, sid: int):
    return _short_file(vid, sid, "thumb", "image/jpeg")


@app.get("/stats", dependencies=[Depends(require_key)])
def stats():
    usage = shutil.disk_usage(config.DATA_DIR)
    return {"videos": len(store.list_videos()),
            "disk_free_gb": round(usage.free / 1e9, 2),
            "whisper_model": config.WHISPER_MODEL}


@app.get("/system", dependencies=[Depends(require_key)])
def system():
    """Configuração efetiva (mostrada na interface desktop)."""
    loaded = transcribe._whisper_model.cache_info().currsize > 0
    return {
        "desktop": config.DESKTOP_MODE,
        "formats": config.FORMATS,
        "whisper_model": config.WHISPER_MODEL,
        "whisper_device": transcribe.describe_device() if loaded else config.WHISPER_DEVICE,
        "video_encoder": render.video_encoder(),
        "data_dir": str(config.DATA_DIR),
        "disk_free_gb": round(shutil.disk_usage(config.DATA_DIR).free / 1e9, 1),
    }


@app.post("/videos/{vid}/open-folder", status_code=204, dependencies=[Depends(require_key)])
def open_folder(vid: str):
    """Só no modo desktop: abre a pasta dos shorts no Explorer."""
    if not config.DESKTOP_MODE:
        raise HTTPException(404)
    _video_or_404(vid)
    folder = store.video_dir(vid) / "shorts"
    if sys.platform == "win32":
        os.startfile(folder)  # noqa: S606 - caminho controlado pelo servidor
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])


# Interface web local (desktop/web): registrada por último para não encobrir a API
if config.DESKTOP_MODE and config.WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=config.WEB_DIR, html=True), name="web")
