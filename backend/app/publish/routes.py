"""Rotas da publicação: agenda de horários, fila e conexão com o YouTube."""
import html
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from .. import config, jobs, store
from ..auth import require_key
from . import queue, youtube

router = APIRouter()
key = [Depends(require_key)]


# ---------------------------------------------------------------- agenda

class SettingsPatch(BaseModel):
    slots: list[str] = Field(..., min_length=1, max_length=12)


@router.get("/publish/settings", dependencies=key)
def get_settings():
    slots = queue.current_slots()
    return {"slots": slots, "tz": config.PUBLISH_TZ, "hashtags": config.PUBLISH_HASHTAGS,
            "next_slots": [queue.iso(d) for d in
                           queue.next_free_slots(3, queue.taken_slots(), slots)],
            "youtube": youtube.status()}


@router.put("/publish/settings", dependencies=key)
def put_settings(body: SettingsPatch):
    try:
        queue.save_slots(body.slots)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return get_settings()


# ---------------------------------------------------------------- fila

class ScheduleRequest(BaseModel):
    video_id: str
    # sem short_ids: todos os cortes prontos do vídeo no formato pedido
    short_ids: list[int] | None = None
    format: str = "9:16"
    slot_at: str | None = None  # ISO com fuso; só para um corte


@router.get("/publish/queue", dependencies=key)
def get_queue(include_done: bool = False):
    items = queue.list_items()
    if not include_done:
        cutoff = time.time() - 3 * 24 * 3600  # postados nos últimos 3 dias continuam visíveis
        items = [i for i in items if i["status"] in queue.ACTIVE or i["status"] == "failed"
                 or (i.get("posted_at") or 0) > cutoff]
    return [queue.item_view(i) for i in items]


@router.post("/publish/queue", status_code=201, dependencies=key)
def add_to_queue(req: ScheduleRequest):
    try:
        shorts = store.get_shorts(req.video_id)
        store.get_video(req.video_id)
    except KeyError:
        raise HTTPException(404, "vídeo não encontrado")
    ids = req.short_ids
    if ids is None:
        ids = [s["id"] for s in shorts if s.get("format", "9:16") == req.format
               and s["render"].get("status") == "done"]
        if not ids:
            raise HTTPException(422, f"nenhum corte {req.format} pronto neste vídeo")
    auto_upload = youtube.status()["auto_upload"]
    try:
        items = queue.schedule(req.video_id, ids, "api" if auto_upload else "assisted",
                               req.slot_at)
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'\""))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if auto_upload:  # API auditada: sobe já, com publicação programada no horário
        for item in items:
            jobs.submit_upload(item["id"])
    return [queue.item_view(i) for i in items]


class ItemPatch(BaseModel):
    slot_at: str | None = None
    title: str | None = Field(None, min_length=1, max_length=queue.TITLE_MAX)
    description: str | None = Field(None, max_length=queue.DESCRIPTION_MAX)
    status: Literal["scheduled", "posted", "skipped"] | None = None


@router.patch("/publish/queue/{item_id}", dependencies=key)
def patch_item(item_id: str, patch: ItemPatch):
    item = _item_or_404(item_id)
    sent = item["status"] in ("uploading", "uploaded")
    if sent and (patch.slot_at or patch.title or patch.description):
        raise HTTPException(409, "já enviado ao YouTube: altere pelo YouTube Studio")
    fields = {}
    if patch.slot_at:
        try:
            when = queue.parse_iso(patch.slot_at)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        if when.timestamp() <= time.time():
            raise HTTPException(422, "o horário precisa estar no futuro")
        fields["slot_at"] = queue.iso(when)
    if patch.title is not None:
        fields["title"] = patch.title.strip()
    if patch.description is not None:
        fields["description"] = patch.description.strip()
    if patch.status:
        fields["status"] = patch.status
        fields["posted_at"] = time.time() if patch.status == "posted" else None
    return queue.item_view(queue.update_item(item_id, **fields))


@router.delete("/publish/queue/{item_id}", status_code=204, dependencies=key)
def delete_item(item_id: str):
    item = _item_or_404(item_id)
    if item["status"] == "uploading":
        raise HTTPException(409, "envio em andamento")
    queue.delete_item(item_id)


@router.post("/publish/queue/{item_id}/upload", dependencies=key)
def upload_item(item_id: str):
    """Envio manual. Sem auditoria o YouTube deixa o vídeo privado (serve para testar)."""
    item = _item_or_404(item_id)
    if not youtube.status()["connected"]:
        raise HTTPException(409, "conecte o canal do YouTube primeiro")
    if item["status"] in ("uploading", "uploaded"):
        raise HTTPException(409, "já enviado")
    jobs.submit_upload(item_id)
    return queue.item_view(queue.get_item(item_id))


def _item_or_404(item_id: str) -> dict:
    try:
        return queue.get_item(item_id)
    except KeyError:
        raise HTTPException(404, "item não encontrado na fila")


# ---------------------------------------------------------------- YouTube

@router.get("/youtube/status", dependencies=key)
def yt_status():
    return {**youtube.status(), "redirect_uri": youtube.redirect_uri()
            if config.PUBLIC_URL else None}


@router.get("/youtube/connect", dependencies=key)
def yt_connect(redirect: bool = False):
    """URL de login do Google. Com ?redirect=true redireciona direto (para abrir no navegador)."""
    try:
        url = youtube.start_auth()
    except youtube.YouTubeError as exc:
        raise HTTPException(409, str(exc))
    return RedirectResponse(url) if redirect else {"url": url}


@router.get("/youtube/callback", response_class=HTMLResponse)
def yt_callback(state: str = "", code: str = "", error: str = ""):
    """Retorno do Google (sem API key: é o navegador voltando; o state protege a troca)."""
    if error or not code:
        return _page("Conexão cancelada", f"O Google respondeu: {error or 'sem código'}.")
    try:
        info = youtube.finish_auth(state, code)
    except youtube.YouTubeError as exc:
        return _page("Não deu certo", str(exc))
    except Exception as exc:  # erro do Google na troca do código
        return _page("Não deu certo", f"Falha ao concluir o login: {exc}")
    return _page("Canal conectado ✔", f"{info.get('title') or 'Canal'} está conectado. "
                 "Pode fechar esta página e voltar ao app.")


@router.post("/youtube/disconnect", status_code=204, dependencies=key)
def yt_disconnect():
    youtube.disconnect()


def _page(title: str, text: str) -> str:
    return (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            f"<title>{html.escape(title)}</title>"
            f"<body style='font-family:system-ui;max-width:520px;margin:15vh auto;padding:0 16px'>"
            f"<h1>{html.escape(title)}</h1><p>{html.escape(text)}</p>")
