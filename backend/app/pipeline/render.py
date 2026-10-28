"""Render de um short: um único comando ffmpeg a partir do JSON de edição.

Cada clip entra como uma entrada separada com -ss/-t antes do -i (busca rápida
por keyframe + decodificação só do necessário), depois tudo é concatenado,
recebe as legendas ASS e o áudio é normalizado para o padrão das redes (-14 LUFS).
Uma única codificação = qualidade melhor e mais rápido do que cortar e juntar.
"""
import logging
import subprocess
from functools import lru_cache
from pathlib import Path

from .. import config
from .captions import build_ass
from .edit import map_words_to_output
from .media import FFmpegError, run

log = logging.getLogger("render")
AUDIO_FADE_S = 0.02  # evita estalos nos cortes
FACE_Y = 0.38  # recorte vertical (vídeo em pé -> 1:1): rostos ficam no terço de cima


def _even(v: float) -> int:
    return int(v) // 2 * 2


def out_size(short: dict) -> tuple[int, int]:
    return config.FORMAT_SIZES[short.get("format", "9:16")]


def crop_box(sw: int, sh: int, out_w: int, out_h: int, center_x: float) -> tuple[int, int, int, int]:
    """Maior retângulo com a proporção de saída dentro do quadro original."""
    target = out_w / out_h
    if sw / sh > target:  # original mais largo: corta nas laterais, seguindo o rosto
        cw, ch = min(_even(sh * target), _even(sw)), _even(sh)
        x = _even(min(max(center_x * sw - cw / 2, 0), sw - cw))
        return cw, ch, x, 0
    cw, ch = _even(sw), min(_even(sw / target), _even(sh))  # mais alto: corta em cima/embaixo
    y = _even(min(max(FACE_Y * sh - ch / 2, 0), sh - ch))
    return cw, ch, 0, y


def _video_chain(i: int, short: dict, meta: dict, clip_idx: int) -> str:
    W, H = out_size(short)
    tail = f"setsar=1,fps={config.OUT_FPS},format=yuv420p,setpts=PTS-STARTPTS[v{i}]"
    mode = short["reframe"]["mode"]

    if mode == "crop":
        centers = short["reframe"]["centers"]
        center = centers[clip_idx] if clip_idx < len(centers) else 0.5
        cw, ch, x, y = crop_box(meta["width"], meta["height"], W, H, center)
        return f"[{i}:v]crop={cw}:{ch}:{x}:{y},scale={W}:{H}:flags=lanczos,{tail}"
    if mode == "fit":
        return (f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,{tail}")
    # blur: fundo desfocado + vídeo inteiro no meio
    return (f"[{i}:v]split[bg{i}][fg{i}];"
            f"[bg{i}]scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,"
            f"crop={W // 4}:{H // 4},boxblur=12:2,scale={W}:{H}[bgb{i}];"
            f"[fg{i}]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs{i}];"
            f"[bgb{i}][fgs{i}]overlay=(W-w)/2:(H-h)/2,{tail}")


@lru_cache(maxsize=1)
def nvenc_available() -> bool:
    """Testa de verdade: o ffmpeg precisa ter o encoder E existir uma placa NVIDIA."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-v", "error", "-f", "lavfi", "-i", "color=s=256x256:d=0.2",
         "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode == 0


def video_encoder() -> str:
    enc = config.VIDEO_ENCODER
    if enc == "auto":
        enc = "h264_nvenc" if nvenc_available() else "libx264"
    return enc


def _codec_args() -> list[str]:
    if video_encoder() == "h264_nvenc":
        # VBR com qualidade constante (-cq), equivalente ao -crf do x264
        return ["-c:v", "h264_nvenc", "-preset", config.NVENC_PRESET, "-tune", "hq",
                "-rc", "vbr", "-cq", config.NVENC_CQ, "-b:v", "0", "-profile:v", "high",
                "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", config.X264_PRESET, "-crf", config.X264_CRF,
            "-profile:v", "high", "-pix_fmt", "yuv420p"]


def build_command(source: Path, short: dict, meta: dict, ass_name: str | None,
                  out_path: Path) -> list[str]:
    clips = short["clips"]
    cmd = ["ffmpeg", "-y", "-hide_banner", "-v", "error", "-progress", "pipe:1", "-nostats"]
    for c in clips:
        cmd += ["-ss", f"{c['in']:.3f}", "-t", f"{c['out'] - c['in']:.3f}", "-i", str(source)]

    parts = []
    for i, c in enumerate(clips):
        dur = c["out"] - c["in"]
        parts.append(_video_chain(i, short, meta, i))
        parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,"
                     f"afade=t=in:d={AUDIO_FADE_S},"
                     f"afade=t=out:st={max(dur - AUDIO_FADE_S, 0):.3f}:d={AUDIO_FADE_S},"
                     f"asetpts=PTS-STARTPTS[a{i}]")
    joined = "".join(f"[v{i}][a{i}]" for i in range(len(clips)))
    parts.append(f"{joined}concat=n={len(clips)}:v=1:a=1[vc][ac]")
    if ass_name:
        parts.append(f"[vc]subtitles={ass_name}[vout]")
    else:
        parts.append("[vc]null[vout]")
    parts.append("[ac]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")

    cmd += ["-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "[aout]",
            *_codec_args(),
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_path)]
    return cmd


def _run_ffmpeg(cmd: list[str], cwd: Path, total: float, on_progress) -> None:
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    for line in proc.stdout:
        if on_progress and line.startswith("out_time_us=") and total:
            try:
                on_progress(min(int(line.split("=")[1]) / 1e6 / total, 1.0))
            except ValueError:
                pass
    err = proc.stderr.read()
    if proc.wait() != 0:
        raise FFmpegError(f"render falhou:\n{err[-2000:]}")


def render_short(source: Path, short: dict, meta: dict, words: list[dict],
                 out_dir: Path, on_progress=None, version: int = 1) -> dict:
    """Gera <out_dir>/short_<id>_v<versão>.mp4 e .jpg. Retorna nomes relativos a out_dir.

    Cada versão vai para um arquivo novo: no Windows não dá para sobrescrever um
    MP4 que o navegador está tocando, e o nome novo também evita cache velho.
    """
    if not short["clips"]:
        raise ValueError("short sem clips (nenhuma fala no trecho?)")
    out_dir.mkdir(parents=True, exist_ok=True)
    sid = short["id"]
    stem = f"short_{sid}_v{version}"
    mp4, jpg, ass = f"{stem}.mp4", f"{stem}.jpg", f"short_{sid}.ass"
    W, H = out_size(short)

    ass_name = None
    cta = short.get("cta") or {}  # shorts antigos não têm o campo
    cta_text = cta.get("text") if cta.get("enabled") else None
    if short["captions"]["enabled"] or short["title_overlay"]["enabled"] or cta_text:
        out_words = map_words_to_output(words, short["clips"])
        title = short["title"] if short["title_overlay"]["enabled"] else None
        (out_dir / ass).write_text(
            build_ass(out_words, title, short["title_overlay"]["seconds"],
                      captions=short["captions"]["enabled"], size=(W, H),
                      cta=cta_text, cta_seconds=config.CTA_SECONDS,
                      total=short["duration"]),
            encoding="utf-8")
        ass_name = ass  # relativo ao cwd: evita escapar caminhos (e o C:\ do Windows)

    tmp = out_dir / f".tmp_{mp4}"
    total = short["duration"]
    try:
        _run_ffmpeg(build_command(source.resolve(), short, meta, ass_name, tmp.name),
                    out_dir, total, on_progress)
    except FFmpegError:
        tmp.unlink(missing_ok=True)
        if video_encoder() != "h264_nvenc":
            raise
        # NVENC pode falhar (driver antigo, sessões esgotadas): tenta de novo na CPU
        log.warning("NVENC falhou no short %s; refazendo com libx264", sid)
        nvenc_available.cache_clear()
        config.VIDEO_ENCODER = "libx264"
        _run_ffmpeg(build_command(source.resolve(), short, meta, ass_name, tmp.name),
                    out_dir, total, on_progress)
    tmp.replace(out_dir / mp4)

    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{min(1.5, total / 2):.2f}",
         "-i", str(out_dir / mp4), "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4",
         str(out_dir / jpg)])
    _remove_old_versions(out_dir, sid, keep=stem)
    return {"file": mp4, "thumb": jpg}


def _remove_old_versions(out_dir: Path, sid: int, keep: str) -> None:
    for old in list(out_dir.glob(f"short_{sid}_v*.*")) + list(out_dir.glob(f"short_{sid}.mp4")) \
            + list(out_dir.glob(f"short_{sid}.jpg")):
        if old.stem != keep:
            try:
                old.unlink()
            except OSError:  # Windows: arquivo aberto no player; fica para a próxima
                pass
