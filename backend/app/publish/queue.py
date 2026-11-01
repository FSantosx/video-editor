"""Fila de publicação: encaixa cortes nos horários (12h, 18h, 21h...) e guarda o que postar.

Cada item da fila:
    {"id", "video_id", "short_id", "slot_at" (ISO UTC), "title", "description", "tags",
     "status": scheduled | posted | skipped | uploading | uploaded | failed,
     "mode": "assisted" | "api", "youtube_id", "error", "created_at", "posted_at"}

Modo assistido: o app lembra no horário e você posta pelo app do YouTube (título e
descrição prontos para copiar). Modo API: o vídeo sobe na hora com publicação
programada (publishAt) e o próprio YouTube publica no horário.
"""
import re
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

from .. import config, store

_lock = threading.RLock()
ACTIVE = ("scheduled", "uploading", "uploaded")
TITLE_MAX = 100  # limite do YouTube
DESCRIPTION_MAX = 5000
STOPWORDS = set("""a o e é de da do das dos que em no na nos nas um uma para pra por com não
se eu você ele ela isso essa esse esta este foi ser ter tem mais muito como mas ou já ao aos
the and""".split())


def _path():
    return config.DATA_DIR / "publish.json"


def _load() -> list[dict]:
    return store._read(_path(), [])


def _save(items: list[dict]) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    store._write(_path(), items)


def list_items() -> list[dict]:
    return sorted(_load(), key=lambda i: i["slot_at"])


def get_item(item_id: str) -> dict:
    for i in _load():
        if i["id"] == item_id:
            return i
    raise KeyError(item_id)


def update_item(item_id: str, **fields) -> dict:
    with _lock:
        items = _load()
        for i in items:
            if i["id"] == item_id:
                i.update(fields)
                _save(items)
                return i
    raise KeyError(item_id)


def delete_item(item_id: str) -> None:
    with _lock:
        items = _load()
        kept = [i for i in items if i["id"] != item_id]
        if len(kept) == len(items):
            raise KeyError(item_id)
        _save(kept)


# ---------------------------------------------------------------- horários

def _settings_path():
    return config.DATA_DIR / "publish_settings.json"


def current_slots() -> list[str]:
    """Horários salvos pelo app (ou os padrões de PUBLISH_SLOTS)."""
    saved = store._read(_settings_path(), {}) or {}
    return saved.get("slots") or list(config.PUBLISH_SLOTS)


def save_slots(slots: list[str]) -> list[str]:
    normalized = [t.strftime("%H:%M") for t in parse_slots(slots)]
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    store._write(_settings_path(), {"slots": normalized})
    return normalized


def parse_slots(slots: list[str]) -> list[dtime]:
    out = []
    for s in slots:
        m = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", s.strip())
        if not m:
            raise ValueError(f"horário inválido: {s!r} (use HH:MM)")
        out.append(dtime(int(m.group(1)), int(m.group(2))))
    if not out:
        raise ValueError("defina pelo menos um horário")
    return sorted(set(out))


def next_free_slots(n: int, taken: set[str], slots: list[str] | None = None,
                    now: datetime | None = None, min_lead: timedelta = timedelta(minutes=20)
                    ) -> list[datetime]:
    """Próximos n horários livres (UTC), a partir de agora + min_lead, no fuso da agenda."""
    tz = ZoneInfo(config.PUBLISH_TZ)
    times = parse_slots(slots or current_slots())
    now = now or datetime.now(timezone.utc)
    earliest = now + min_lead
    day = earliest.astimezone(tz).date()
    found: list[datetime] = []
    while len(found) < n:
        for t in times:
            local = datetime.combine(day, t, tzinfo=tz)
            utc = local.astimezone(timezone.utc)
            if utc >= earliest and iso(utc) not in taken:
                found.append(utc)
                if len(found) == n:
                    break
        day += timedelta(days=1)
    return found


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("informe o fuso no horário (ex.: 2026-11-02T15:00:00Z)")
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------- metadados

def build_tags(text: str, limit: int = 8) -> list[str]:
    """Palavras mais frequentes do trecho (sem stopwords) viram tags."""
    words = [w.lower() for w in re.findall(r"[\wÀ-ÿ]{4,}", text)]
    counts = Counter(w for w in words if w not in STOPWORDS)
    return [w for w, _ in counts.most_common(limit)]


def build_metadata(short: dict, video: dict) -> dict:
    """Título, descrição e tags prontos para o YouTube a partir do corte."""
    title = re.sub(r"[<>]", "", short.get("title") or "").strip()[:TITLE_MAX] or "Corte"
    hashtags = config.PUBLISH_HASHTAGS.strip()
    tags = build_tags(short.get("text", ""))
    body = short.get("text", "").strip()
    if len(body) > 280:
        body = body[:280].rsplit(" ", 1)[0] + "…"
    cta = (short.get("cta") or {}).get("text") or config.CTA_TEXT
    parts = [title, "", f"“{body}”" if body else "", "", cta, "",
             " ".join([hashtags] + [f"#{t}" for t in tags[:3]]).strip()]
    description = "\n".join(p for p in parts if p is not None).strip()
    description = re.sub(r"\n{3,}", "\n\n", description)[:DESCRIPTION_MAX]
    return {"title": title, "description": description, "tags": tags}


# ---------------------------------------------------------------- fila

def schedule(video_id: str, short_ids: list[int], mode: str,
             slot_at: str | None = None) -> list[dict]:
    """Coloca cortes na fila, cada um no próximo horário livre (ou no slot_at informado)."""
    video = store.get_video(video_id)
    shorts = {s["id"]: s for s in store.get_shorts(video_id)}
    missing = [sid for sid in short_ids if sid not in shorts]
    if missing:
        raise KeyError(f"cortes não encontrados: {missing}")
    not_ready = [sid for sid in short_ids if shorts[sid]["render"].get("status") != "done"]
    if not_ready:
        raise ValueError(f"cortes ainda não renderizados: {not_ready}")

    with _lock:
        items = _load()
        already = {(i["video_id"], i["short_id"]) for i in items if i["status"] in ACTIVE}
        dupes = [sid for sid in short_ids if (video_id, sid) in already]
        if dupes:
            raise ValueError(f"cortes já estão na fila: {dupes}")
        taken = {i["slot_at"] for i in items if i["status"] in ACTIVE}
        if slot_at:
            if len(short_ids) != 1:
                raise ValueError("horário específico só para um corte por vez")
            when = parse_iso(slot_at)
            if when <= datetime.now(timezone.utc):
                raise ValueError("o horário precisa estar no futuro")
            slots = [when]
        else:
            slots = next_free_slots(len(short_ids), taken)

        new = []
        for sid, when in zip(short_ids, slots):
            meta = build_metadata(shorts[sid], video)
            new.append({
                "id": uuid.uuid4().hex[:12], "video_id": video_id, "short_id": sid,
                "format": shorts[sid].get("format", "9:16"), "slot_at": iso(when),
                **meta, "status": "scheduled", "mode": mode, "youtube_id": None,
                "error": None, "created_at": time.time(), "posted_at": None,
            })
        _save(items + new)
        return new


def taken_slots() -> set[str]:
    return {i["slot_at"] for i in _load() if i["status"] in ACTIVE}


def item_view(item: dict) -> dict:
    """Item + dados do corte (miniatura, duração) para as telas."""
    try:
        short = store.get_short(item["video_id"], item["short_id"])
        extra = {"hook": short.get("hook", ""), "duration": short.get("duration"),
                 "render_version": short["render"].get("version", 0)}
    except KeyError:
        extra = {"missing": True}  # vídeo/corte apagado depois de agendado
    return {**item, **extra}

