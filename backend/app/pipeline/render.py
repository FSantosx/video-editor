"""Render de um short: um único comando ffmpeg a partir do JSON de edição.

Cada clip entra como uma entrada separada com -ss/-t antes do -i (busca rápida
por keyframe + decodificação só do necessário), depois tudo é concatenado,
recebe as legendas ASS e o áudio é normalizado para o padrão das redes (-14 LUFS).
Uma única codificação = qualidade melhor e mais rápido do que cortar e juntar.
"""
import subprocess
from pathlib import Path

from .. import config
from .captions import build_ass
from .edit import map_words_to_output
from .media import FFmpegError, run

AUDIO_FADE_S = 0.02  # evita estalos nos cortes


def _even(v: float) -> int:
    return int(v) // 2 * 2


def _video_chain(i: int, short: dict, meta: dict, clip_idx: int) -> str:
    W, H, FPS = config.OUT_W, config.OUT_H, config.OUT_FPS
    tail = f"setsar=1,fps={FPS},format=yuv420p,setpts=PTS-STARTPTS[v{i}]"
    mode = short["reframe"]["mode"]

    if mode == "crop":
        sw, sh = meta["width"], meta["height"]
        cw = min(_even(sh * 9 / 16), _even(sw))
        center = short["reframe"]["centers"][clip_idx]
        x = _even(min(max(center * sw - cw / 2, 0), sw - cw))
        return f"[{i}:v]crop={cw}:{sh}:{x}:0,scale={W}:{H}:flags=lanczos,{tail}"
    if mode == "fit":
        return (f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,{tail}")
    # blur: fundo desfocado + vídeo inteiro no meio
    return (f"[{i}:v]split[bg{i}][fg{i}];"
            f"[bg{i}]scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,"
            f"crop={W // 4}:{H // 4},boxblur=12:2,scale={W}:{H}[bgb{i}];"
            f"[fg{i}]scale={W}:-2[fgs{i}];"
            f"[bgb{i}][fgs{i}]overlay=(W-w)/2:(H-h)/2,{tail}")


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
            "-c:v", "libx264", "-preset", config.X264_PRESET, "-crf", config.X264_CRF,
            "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_path)]
    return cmd


def render_short(source: Path, short: dict, meta: dict, words: list[dict],
                 out_dir: Path, on_progress=None) -> dict:
    """Gera <out_dir>/short_<id>.mp4 e .jpg. Retorna caminhos relativos a out_dir."""
    if not short["clips"]:
        raise ValueError("short sem clips (nenhuma fala no trecho?)")
    out_dir.mkdir(parents=True, exist_ok=True)
    sid = short["id"]
    mp4, jpg, ass = f"short_{sid}.mp4", f"short_{sid}.jpg", f"short_{sid}.ass"

    ass_name = None
    if short["captions"]["enabled"] or short["title_overlay"]["enabled"]:
        out_words = map_words_to_output(words, short["clips"])
        title = short["title"] if short["title_overlay"]["enabled"] else None
        (out_dir / ass).write_text(build_ass(out_words, title, short["title_overlay"]["seconds"],
                                             captions=short["captions"]["enabled"]))
        ass_name = ass  # relativo ao cwd: evita escapar caminhos no filtro subtitles

    tmp = out_dir / f".tmp_{mp4}"
    cmd = build_command(source.resolve(), short, meta, ass_name, tmp.name)
    total = short["duration"]
    proc = subprocess.Popen(cmd, cwd=out_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)
    for line in proc.stdout:
        if on_progress and line.startswith("out_time_us=") and total:
            try:
                on_progress(min(int(line.split("=")[1]) / 1e6 / total, 1.0))
            except ValueError:
                pass
    err = proc.stderr.read()
    if proc.wait() != 0:
        tmp.unlink(missing_ok=True)
        raise FFmpegError(f"render falhou:\n{err[-2000:]}")
    tmp.replace(out_dir / mp4)

    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{min(1.5, total / 2):.2f}",
         "-i", str(out_dir / mp4), "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4",
         str(out_dir / jpg)])
    return {"file": mp4, "thumb": jpg}
