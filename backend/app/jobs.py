"""Fila de processamento em threads (suficiente para um único container no Railway).

analyze_video: áudio -> transcrição -> silêncios/energia -> seleção -> JSON dos shorts
               e já enfileira o render de cada short.
render:        gera o MP4 de um short a partir do JSON de edição.
"""
import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config, store
from .pipeline import media
from .pipeline.edit import build_short, render_clips
from .pipeline.teaser import apply_loop, build_teaser
from .pipeline.titles import generate_titles
from .pipeline.reframe import compute_reframe
from .pipeline.render import render_short
from .pipeline.select import select_shorts
from .pipeline.transcribe import transcribe

log = logging.getLogger("jobs")
_pool = ThreadPoolExecutor(max_workers=config.WORKERS, thread_name_prefix="job")

# Peso de cada etapa no progresso total da análise
STEPS = {"probe": (0.0, 0.02), "audio": (0.02, 0.08), "transcribe": (0.08, 0.85),
         "analyze": (0.85, 0.92), "select": (0.92, 1.0)}


def _progress(vid: str, step: str, frac: float = 0.0) -> None:
    lo, hi = STEPS[step]
    store.update_video(vid, step=step, progress=round(lo + (hi - lo) * frac, 3))


def submit_analysis(vid: str) -> None:
    store.update_video(vid, status="queued", step=None, progress=0.0, error=None)
    _pool.submit(_safe, analyze_video, vid)


def submit_render(vid: str, sid: int) -> None:
    def mark(s):
        s["render"].update(status="queued", error=None, progress=0.0)
    store.update_short(vid, sid, mark)
    _pool.submit(_safe, render, vid, sid)


def _safe(fn, *args):
    try:
        fn(*args)
    except Exception as exc:  # o job nunca derruba o servidor
        log.error("job %s%s falhou\n%s", fn.__name__, args, traceback.format_exc())
        vid = args[0]
        try:
            if fn is analyze_video:
                store.update_video(vid, status="error", error=str(exc)[-500:])
            else:
                store.update_short(vid, args[1], lambda s: s["render"].update(
                    status="error", error=str(exc)[-500:]))
        except KeyError:
            pass  # vídeo apagado no meio do processamento


def analyze_video(vid: str) -> None:
    t0 = time.time()
    store.update_video(vid, status="analyzing")
    src = store.source_path(vid)
    d = store.video_dir(vid)

    _progress(vid, "probe")
    meta = media.probe(src)
    store.update_video(vid, meta=meta)

    analysis = store.get_analysis(vid)
    if analysis is None:  # cache: reanalisar não transcreve de novo
        _progress(vid, "audio")
        wav = media.extract_audio(src, d / "audio.wav")

        _progress(vid, "transcribe")
        words, language = transcribe(wav, src, lambda f: _progress(vid, "transcribe", f))

        _progress(vid, "analyze")
        analysis = {"words": words, "language": language,
                    "silences": media.detect_silences(wav),
                    "energy": media.audio_energy(wav)}
        store.save_analysis(vid, analysis)
        wav.unlink(missing_ok=True)

    _progress(vid, "select")
    words = analysis["words"]
    # O teaser soma até TEASER_MAX_S à duração: desconta do alvo para o total ficar perto dele.
    # No loop o teaser só muda de lugar (o corte termina antes dele), então não soma nada.
    adds_teaser = config.TEASER_ENABLED and not config.LOOP_ENABLED
    target = config.SHORT_TARGET_S - (0.8 * config.TEASER_MAX_S if adds_teaser else 0)
    if config.LOOP_ENABLED:  # o fim depois do teaser é cortado: trechos um pouco mais longos
        target += 4
    candidates = select_shorts(words, analysis["energy"], target_s=target)
    teasers = [build_teaser(words, analysis["energy"], c.get("segments") or [c])
               for c in candidates]
    # Títulos de gancho (Claude se houver chave; senão heurística), uma chamada por vídeo
    video = store.get_video(vid)
    titles = generate_titles(
        [{"text": c["text"], "teaser": t["text"] or None} for c, t in zip(candidates, teasers)],
        context=Path(video["filename"]).stem.replace("_", " "))
    for cand, t in zip(candidates, titles):
        cand.update(title=t["title"], hook=t["hook"], titles_source=t["source"])
    # Um short por formato para cada trecho; o group liga as versões do mesmo trecho
    shorts, next_id = [], 1
    for group, (cand, teaser) in enumerate(zip(candidates, teasers), start=1):
        for fmt in config.FORMATS:
            short = build_short(next_id, cand, words, fmt=fmt, group=group, teaser=teaser)
            apply_loop(short)
            shorts.append(short)
            next_id += 1
    store.save_shorts(vid, shorts)
    store.update_video(vid, status="ready", step=None, progress=1.0,
                       pipeline_version=config.PIPELINE_VERSION,
                       language=analysis.get("language"),
                       analysis_seconds=round(time.time() - t0, 1))
    log.info("vídeo %s analisado em %.1fs: %d trechos, %d shorts",
             vid, time.time() - t0, len(candidates), len(shorts))

    # Primeiro todos do formato principal, para o usuário já ter o que ver
    for fmt in config.FORMATS:
        for s in shorts:
            if s["format"] == fmt:
                submit_render(vid, s["id"])


def render(vid: str, sid: int) -> None:
    t0 = time.time()
    src = store.source_path(vid)
    meta = store.get_video(vid)["meta"]
    words = store.get_analysis(vid)["words"]
    short = store.get_short(vid, sid)
    version = short["render"].get("version", 0)

    def set_status(**kw):
        store.update_short(vid, sid, lambda s: s["render"].update(**kw))

    set_status(status="rendering", progress=0.0)
    if short["reframe"]["mode"] == "auto":
        reframe = _sibling_reframe(vid, short, meta) or compute_reframe(
            src, render_clips(short), meta["width"], meta["height"], target_aspect=_aspect(short))
        store.update_short(vid, sid, lambda s: s.update(reframe=reframe))
        short["reframe"] = reframe

    last = [0.0]

    def on_progress(f):
        if f - last[0] >= 0.05:  # não escrever o JSON a cada frame
            last[0] = f
            set_status(progress=round(f, 2))

    result = render_short(src, short, meta, words, store.video_dir(vid) / "shorts", on_progress,
                          version=version + 1)
    set_status(status="done", progress=1.0, file=result["file"], thumb=result["thumb"],
               version=version + 1, seconds=round(time.time() - t0, 1))
    log.info("short %s/%s (%s) renderizado em %.1fs", vid, sid, short.get("format"),
             time.time() - t0)


def _aspect(short: dict) -> float:
    w, h = config.FORMAT_SIZES[short.get("format", "9:16")]
    return w / h


def _sibling_reframe(vid: str, short: dict, meta: dict) -> dict | None:
    """Reaproveita a detecção de rosto de outro formato do mesmo trecho (mesmos clips).

    Só vale quando os dois formatos cortam nas laterais (original mais largo que
    ambos), caso em que o centro X do rosto é o mesmo.
    """
    src_aspect = meta["width"] / meta["height"]
    if src_aspect <= _aspect(short):
        return None
    for other in store.get_shorts(vid):
        if (other["id"] != short["id"] and other.get("group") == short.get("group")
                and render_clips(other) == render_clips(short) and src_aspect > _aspect(other)
                and other["reframe"]["mode"] in ("crop", "blur")):
            return {"mode": other["reframe"]["mode"], "centers": list(other["reframe"]["centers"])}
    return None


def resume_pending() -> None:
    """Depois de um restart do container, retoma o que ficou pela metade."""
    for v in store.list_videos():
        if v["status"] in ("queued", "analyzing"):
            submit_analysis(v["id"])
        elif v["status"] == "ready":
            for s in store.get_shorts(v["id"]):
                if s["render"]["status"] in ("pending", "queued", "rendering"):
                    submit_render(v["id"], s["id"])
        elif v["status"] == "uploading":
            store.delete_video(v["id"])  # upload interrompido
