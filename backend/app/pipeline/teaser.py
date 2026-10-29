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


def _cut_offset(t: float, clips: list[dict]) -> float:
    """Posição de t (tempo do original) no corte já editado (sem as pausas cortadas)."""
    offset = 0.0
    for c in clips:
        if c["out"] <= t:
            offset += c["out"] - c["in"]
        elif c["in"] < t:
            offset += t - c["in"]
    return offset


def _candidate_spans(ws: list[dict], max_s: float, include_tail: bool):
    """Trechos de uma frase que podem virar teaser: (palavras, frase_inteira, é_final).

    - frase inteira, se couber em max_s
    - senão, o começo da frase até max_s (corte no meio da ideia gera curiosidade)
    - no loop, também o FINAL da frase: o corte termina no meio dela e, ao recomeçar,
      o teaser completa exatamente a frase (emenda perfeita)
    """
    if speech_duration(ws) <= max_s:
        yield ws, True, False
        return
    head = []
    for w in ws:
        if w["end"] - ws[0]["start"] > max_s:
            break
        head.append(w)
    yield head, False, False
    if include_tail:
        tail = []
        for w in reversed(ws):
            if ws[-1]["end"] - w["start"] > max_s:
                break
            tail.insert(0, w)
        yield tail, True, True


def pick_teaser(words: list[dict], energy: list[float], segments: list[dict],
                max_s: float = config.TEASER_MAX_S,
                earliest: float = EARLIEST_FRACTION,
                loop_min_s: float | None = None) -> dict | None:
    """Escolhe o trecho do teaser. Retorna {"start", "end", "text"} (tempo do original) ou None.

    loop_min_s: só aceita teasers que, no final em loop, deixem o corte com pelo menos esse
    tanto. A conta usa o tempo EDITADO (sem as pausas), igual à verificação do loop: no tempo
    bruto a fala real tem 15-25% de pausas e o loop acabava recusado sem aviso.
    """
    if not segments or not words:
        return None
    sentences, feats, sent_score, _ = score_sentences(words, energy)
    total = sum(g["end"] - g["start"] for g in segments)
    cut_clips = [c for g in segments for c in build_clips(words_in(words, g["start"], g["end"]))]

    best, best_score = None, float("-inf")
    for s, f, score in zip(sentences, feats, sent_score):
        if f["filler"] or not _inside(s, segments):
            continue
        if _output_offset(s["start"], segments) < earliest * total:
            continue
        ws = words[s["word_idx"][0]: s["word_idx"][1]]
        for span, complete, tail in _candidate_spans(ws, max_s, include_tail=loop_min_s is not None):
            if not span or span[-1]["end"] - span[0]["start"] < TEASER_MIN_S:
                continue
            if loop_min_s is not None:
                # corte no loop = tudo antes do teaser (editado) + o próprio teaser
                teaser_len = clips_duration(build_clips(span))
                if _cut_offset(span[0]["start"], cut_clips) + teaser_len < loop_min_s + 0.3:
                    continue
            joined = " ".join(_norm(w["word"]) for w in span)
            bonus = (0.6 * f["exclaim"] + 0.3 * f["question"] + 0.3 * complete
                     + 0.5 * any(f" {c} " in f" {joined} " for c in CONCLUSIVE)
                     - 0.2 * tail)  # leve preferência por frase inteira / começo de frase
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
        # No loop o corte termina no teaser: ele vem do fim do trecho e precisa deixar o
        # corte (editado) com pelo menos LOOP_MIN_S
        found = pick_teaser(words, energy, segments, earliest=config.LOOP_TEASER_FROM,
                            loop_min_s=config.LOOP_MIN_S)
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
    return bool(main) and bool(clips_duration(render_clips(trial)) >= config.LOOP_MIN_S)


def apply_loop(short: dict, enabled: bool = config.LOOP_ENABLED) -> bool:
    """Liga/desliga o final em loop. Retorna se ficou ligado."""
    on = enabled and loop_possible(short)
    short["loop"] = {"enabled": on}
    if enabled and not on:  # explica na interface por que ficou desligado
        teaser = short.get("teaser") or {}
        short["loop"]["reason"] = (
            "sem teaser neste corte" if not (teaser.get("enabled") and teaser.get("clips"))
            else f"o corte ficaria com menos de {config.LOOP_MIN_S:.0f}s")
    update_duration(short)
    return on
