"""Legendas animadas estilo TikTok em formato ASS (renderizadas pelo libass do ffmpeg).

Mostra 1 a 3 palavras por vez, em maiúsculas, com a palavra falada em amarelo
e levemente ampliada. Também desenha o título do short no topo nos primeiros
segundos.
"""
import re

from .. import config

MAX_WORDS = 3
MAX_CHARS = 16
BREAK_GAP_S = 0.3

WHITE = "&H00FFFFFF"
YELLOW = "&H0000E5FF"  # ASS usa BGR
BLACK = "&H00000000"
TITLE_BG = "&H33000000"


def _ts(t: float) -> str:
    t = max(t, 0.0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _clean(word: str) -> str:
    word = re.sub(r"[.,;:…\"“”()\[\]]", "", word).upper()
    return word.replace("\\", "").replace("{", "").replace("}", "")


def _chunks(words: list[dict]) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    for w in words:
        if not _clean(w["word"]):
            continue
        cur = chunks[-1] if chunks else None
        if (cur is None or len(cur) >= MAX_WORDS
                or w["start"] - cur[-1]["end"] > BREAK_GAP_S
                or re.search(r"[.!?…,]$", cur[-1]["word"])
                or len(" ".join(_clean(x["word"]) for x in cur + [w])) > MAX_CHARS):
            chunks.append([w])
        else:
            cur.append(w)
    return chunks


def build_ass(words: list[dict], title: str | None, title_seconds: float,
              captions: bool = True, size: tuple[int, int] = (1080, 1920)) -> str:
    W, H = size
    vertical = H > W
    # Legenda no terço de baixo, acima da interface do app (Reels/TikTok) no 9:16
    caption_margin = int(H * (0.29 if vertical else 0.14))
    title_margin = int(H * (0.12 if vertical else 0.06))
    caption_size = 86 if vertical else 72
    font = config.CAPTION_FONT
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,{font},{caption_size},{WHITE},{WHITE},{BLACK},{BLACK},-1,0,0,0,100,100,0,0,"
        f"1,7,3,2,60,60,{caption_margin},1",
        f"Style: Title,{font},62,{WHITE},{WHITE},{TITLE_BG},{TITLE_BG},-1,0,0,0,100,100,0,0,"
        f"3,18,0,8,80,80,{title_margin},1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    if title and title_seconds > 0:
        safe = title.replace("\\", "").replace("{", "").replace("}", "")
        lines.append(f"Dialogue: 1,{_ts(0)},{_ts(title_seconds)},Title,,0,0,0,,"
                     f"{{\\fad(150,250)}}{safe}")

    if captions:
        chunks = _chunks(words)
        for ci, chunk in enumerate(chunks):
            next_start = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else None
            chunk_end = chunk[-1]["end"] + 0.25
            if next_start is not None:
                chunk_end = min(chunk_end, next_start)
            for wi, w in enumerate(chunk):
                start = w["start"]
                end = chunk[wi + 1]["start"] if wi + 1 < len(chunk) else chunk_end
                if end <= start:
                    continue
                parts = []
                for k, x in enumerate(chunk):
                    txt = _clean(x["word"])
                    if k == wi:
                        parts.append(f"{{\\c{YELLOW}\\fscx112\\fscy112}}{txt}{{\\r}}")
                    else:
                        parts.append(txt)
                lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Caption,,0,0,0,,"
                             + " ".join(parts))
    return "\n".join(lines) + "\n"
