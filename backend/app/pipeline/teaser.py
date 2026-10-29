"""Abertura com teaser ("cold open").

O short começa com 1,2 a 3,5s do momento mais forte do próprio trecho (o
punchline) e depois volta ao início. Ataca quem desliza nos primeiros segundos:
a pessoa vê logo onde a história vai chegar e fica para entender o contexto.

O teaser sai da segunda parte do trecho (senão só repetiria a abertura) e
prefere frases com exclamação, números, ganchos ou tom conclusivo. Se a frase
for longa, usa só o começo dela, terminando numa palavra: o corte no meio da
ideia gera curiosidade ("e foi aí que eu perdi...").
"""
from .. import config
from .edit import build_clips, clips_duration, main_clips, render_clips, update_duration, words_in
from .select import CONCLUSIVE, _norm, score_sentences, speech_duration

TEASER_MIN_S = 1.2
EARLIEST_FRACTION = 0.25  # o teaser não pode vir do primeiro quarto do trecho


def _inside(sentence: dict, segments: list[dict]) -> bool:
    return any(sentence["start"] >= g["start"] - 0.01 and sentence["end"] <= g["end"] + 0.01
               for g in segments)


def _output_offset(t: float, segments: list[dict]) -> float:
    """Posição aproximada de t (tempo do original) dentro do short."""
    offset = 0.0
    for g in segments:
        if t <= g["end"]:
            return offset + max(0.0, t - g["start"])
        offset += g["end"] - g["start"]
    return offset


def pick_teaser(words: list[dict], energy: list[float], segments: list[dict],
                max_s: float = config.TEASER_MAX_S,
                earliest: float = EARLIEST_FRACTION) -> dict | None:
    """Escolhe o trecho do teaser. Retorna {"start", "end", "text"} (tempo do original) ou None."""
    if not segments or not words:
        return None
    sentences, feats, sent_score, _ = score_sentences(words, energy)
    total = sum(g["end"] - g["start"] for g in segments)

    best, best_score = None, float("-inf")
    for s, f, score in zip(sentences, feats, sent_score):
        if f["filler"] or not _inside(s, segments):
            continue
        if _output_offset(s["start"], segments) < earliest * total:
            continue
        ws = words[s["word_idx"][0]: s["word_idx"][1]]
        if speech_duration(ws) <= max_s:
            span, complete = ws, True
        else:
            span = []  # começo da frase até max_s (corte que gera curiosidade)
            for w in ws:
                if w["end"] - ws[0]["start"] > max_s:
                    break
                span.append(w)
            complete = False
        if not span or span[-1]["end"] - span[0]["start"] < TEASER_MIN_S:
            continue
        joined = " ".join(_norm(w["word"]) for w in span)
        bonus = (0.6 * f["exclaim"] + 0.3 * f["question"] + 0.3 * complete
                 + 0.5 * any(f" {c} " in f" {joined} " for c in CONCLUSIVE))
        if score + bonus > best_score:
            best_score = score + bonus
            best = {"start": span[0]["start"], "end": span[-1]["end"],
                    "text": " ".join(w["word"] for w in span)}
    return best


def build_teaser(words: list[dict], energy: list[float], segments: list[dict],
                 enabled: bool = config.TEASER_ENABLED,
                 for_loop: bool = config.LOOP_ENABLED) -> dict:
    """Campo "teaser" do JSON do short.

    for_loop: o teaser sai da parte final do trecho, porque no loop o corte termina
    antes dele (tudo depois do teaser fica de fora).
    """
    found = None
    if for_loop:
        # No loop o corte termina no teaser: ele precisa vir depois de LOOP_MIN_S de fala
        total = sum(g["end"] - g["start"] for g in segments)
        need = (config.LOOP_MIN_S - config.TEASER_MAX_S) / total if total else 1.0
        found = pick_teaser(words, energy, segments,
                            earliest=max(config.LOOP_TEASER_FROM, need))
    if not found:  # sem loop (ou nenhuma frase boa no fim): teaser normal
        found = pick_teaser(words, energy, segments, earliest=EARLIEST_FRACTION)
    if not found:
        return {"enabled": False, "clips": [], "text": ""}
    clips = build_clips(words_in(words, found["start"], found["end"]))
    return {"enabled": enabled and bool(clips), "clips": clips, "text": found["text"]}


def loop_possible(short: dict) -> bool:
    """Loop precisa de teaser ligado e de corte que não fique curto demais."""
    teaser = short.get("teaser") or {}
    if not (teaser.get("enabled") and teaser.get("clips")):
        return False
    trial = {**short, "loop": {"enabled": True}}
    main = main_clips(trial)
    return bool(main) and clips_duration(render_clips(trial)) >= config.LOOP_MIN_S


def apply_loop(short: dict, enabled: bool = config.LOOP_ENABLED) -> bool:
    """Liga/desliga o final em loop. Retorna se ficou ligado."""
    on = enabled and loop_possible(short)
    short["loop"] = {"enabled": on}
    update_duration(short)
    return on
