"""Monta o JSON de edição de um short a partir de um trecho escolhido.

Este JSON é a fonte da verdade: o app edita ele (título, início/fim,
legendas...) e o render só lê ele. Formato:

{
  "id": 1, "group": 1, "format": "9:16",
  "title": "...", "score": 87, "text": "...",
  "window": {"start": 312.4, "end": 355.6},     # trecho no vídeo original
  "clips": [{"in": 312.4, "out": 318.9}, ...],  # pedaços mantidos (pausas removidas)
  "duration": 41.3,                              # duração final
  "reframe": {"mode": "crop", "centers": [0.52, 0.48, ...]},  # 1 centro X (0-1) por clip
  "captions": {"enabled": true},
  "title_overlay": {"enabled": true, "seconds": 3.0},
  "render": {"status": "pending", "file": null, "error": null, "version": 0}
}
"""
import unicodedata

from .. import config

# Só hesitações inequívocas: "é", "tipo", "né" também são palavras normais.
FILLERS = {"hum", "hmm", "hm", "ahn", "ah", "ãh", "eh", "uh", "um", "éé", "ééé", "ahm", "uhm"}
EDGE_PAD_S = 0.08  # respiro antes/depois de cada pedaço para não cortar sílabas


def _bare(word: str) -> str:
    w = word.lower().strip(".,!?…;:\"'()[]-")
    return unicodedata.normalize("NFC", w)


def words_in(words: list[dict], start: float, end: float) -> list[dict]:
    return [w for w in words if w["start"] >= start - 0.01 and w["end"] <= end + 0.01]


def build_clips(words: list[dict], pause_cut: float = config.PAUSE_CUT_S,
                remove_fillers: bool = True) -> list[dict]:
    kept = [w for w in words if not (remove_fillers and _bare(w["word"]) in FILLERS)]
    if not kept:
        return []
    groups = [[kept[0]]]
    for prev, w in zip(kept, kept[1:]):
        if w["start"] - prev["end"] > pause_cut:
            groups.append([w])
        else:
            groups[-1].append(w)

    clips = []
    for g in groups:
        c_in = max(g[0]["start"] - EDGE_PAD_S, 0.0)
        c_out = g[-1]["end"] + EDGE_PAD_S
        if clips and c_in <= clips[-1]["out"]:
            clips[-1]["out"] = round(c_out, 3)
        else:
            clips.append({"in": round(c_in, 3), "out": round(c_out, 3)})
    return clips


def map_words_to_output(words: list[dict], clips: list[dict]) -> list[dict]:
    """Converte tempos do vídeo original para a linha do tempo do short."""
    out, offset = [], 0.0
    for c in clips:
        for w in words:
            if w["start"] >= c["in"] - 1e-3 and w["end"] <= c["out"] + 1e-3:
                out.append({"word": w["word"],
                            "start": round(offset + w["start"] - c["in"], 3),
                            "end": round(offset + w["end"] - c["in"], 3)})
        offset += c["out"] - c["in"]
    return out


def clips_duration(clips: list[dict]) -> float:
    return round(sum(c["out"] - c["in"] for c in clips), 3)


def build_short(idx: int, candidate: dict, words: list[dict], fmt: str = "9:16",
                group: int | None = None) -> dict:
    # A seleção pode ter cortado frases de bastidor do meio: só usa os segmentos mantidos
    segments = candidate.get("segments") or [candidate]
    clips = []
    for seg in segments:
        clips += build_clips(words_in(words, seg["start"], seg["end"]))
    return {
        "id": idx,
        # mesmo trecho em formatos diferentes (9:16, 1:1) compartilha o group
        "group": group if group is not None else idx,
        "format": fmt,
        "title": candidate["title"],
        "score": candidate["score"],
        "text": candidate["text"],
        "window": {"start": candidate["start"], "end": candidate["end"]},
        "clips": clips,
        "duration": clips_duration(clips),
        "reframe": {"mode": "auto", "centers": []},
        "captions": {"enabled": True},
        "title_overlay": {"enabled": True, "seconds": 3.0},
        "render": {"status": "pending", "file": None, "error": None, "version": 0},
    }


def apply_window(short: dict, words: list[dict], start: float, end: float) -> dict:
    """Usado quando o usuário ajusta início/fim no app: recalcula os cortes."""
    window_words = words_in(words, start, end)
    short["window"] = {"start": round(start, 3), "end": round(end, 3)}
    short["clips"] = build_clips(window_words)
    short["duration"] = clips_duration(short["clips"])
    short["text"] = " ".join(w["word"] for w in window_words)
    short["reframe"] = {"mode": "auto", "centers": []}
    return short
