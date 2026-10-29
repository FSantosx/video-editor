"""Escolha automática de trechos para shorts, sem LLM.

Ideia: quebrar a transcrição em frases, pontuar cada frase com sinais simples
(ritmo de fala, energia do áudio, palavras de gancho) e procurar janelas de
frases consecutivas que, depois de cortadas as pausas e as frases de bastidor
("bom, deixa eu ajustar a câmera"), durem entre SHORT_MIN_S e SHORT_MAX_S.
Por fim, pegar as melhores janelas sem sobreposição.

A interface `select_shorts(words, energy, ...) -> list[dict]` é a mesma que um
seletor com LLM terá no futuro, então dá para trocar sem mexer no resto.
"""
import re
import unicodedata

import numpy as np

from .. import config

SENTENCE_END = re.compile(r"[.!?…]+[\"')\]]*$")
SENTENCE_GAP_S = 0.9
MAX_SENTENCE_WORDS = 30

# Palavras que costumam abrir/sustentar bons ganchos (comparadas sem acento)
HOOK_WORDS = {
    "voce", "voces", "segredo", "erro", "erros", "nunca", "ninguem", "sempre", "pior",
    "melhor", "dica", "dicas", "verdade", "problema", "porque", "como", "atencao",
    "importante", "cuidado", "simples", "rapido", "dinheiro", "resultado", "mudou",
    "descobri", "aprendi", "incrivel", "olha", "imagina", "pare", "sabia", "mentira",
}
ENERGY_WINDOW_S = 0.5
# Pausa longa entre frases costuma ser troca de assunto: evitar que o short atravesse
TOPIC_GAP_S = 1.2
# Frases de transição/bastidor ("bom, agora deixa eu ajustar a câmera") enfraquecem o short
FILLER_OPENERS = ("bom", "enfim", "pronto", "entao", "deixa eu", "deixe eu", "ok", "beleza",
                  "hum", "ne", "e ai")
FILLER_WORDS = {"camera", "microfone", "audio", "ajustar", "gravando", "gravar", "hum"}
# Frases que fecham uma ideia: bons finais (o "punchline")
CONCLUSIVE = ("por isso", "ou seja", "resumindo", "no fim", "no final", "a licao", "o segredo",
              "a verdade", "conclusao", "moral da historia", "e isso", "o importante", "entao e",
              "a dica", "nunca mais", "pra sempre", "para sempre", "foi assim", "aprendi")
# Começos de frase que deixam o final pendurado
DANGLING_OPENERS = ("mas", "e", "porque", "so que", "ai", "tipo", "inclusive", "alem disso", "e ai")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if c.isalnum() and not unicodedata.combining(c))


def split_sentences(words: list[dict]) -> list[dict]:
    sentences, begin = [], 0

    def flush(end: int):
        nonlocal begin
        if end > begin:
            chunk = words[begin:end]
            sentences.append({
                "start": chunk[0]["start"],
                "end": chunk[-1]["end"],
                "text": " ".join(w["word"] for w in chunk),
                "word_idx": (begin, end),
            })
        begin = end

    for i, w in enumerate(words):
        if i > begin and w["start"] - words[i - 1]["end"] > SENTENCE_GAP_S:
            flush(i)
        if SENTENCE_END.search(w["word"]) or i + 1 - begin >= MAX_SENTENCE_WORDS:
            flush(i + 1)
    flush(len(words))
    return sentences


def speech_duration(words: list[dict], pause_cut: float = config.PAUSE_CUT_S) -> float:
    """Duração depois de remover pausas > pause_cut (o que o render vai fazer)."""
    if not words:
        return 0.0
    total = words[0]["end"] - words[0]["start"]
    for prev, w in zip(words, words[1:]):
        gap = w["start"] - prev["end"]
        total += (w["end"] - w["start"]) + min(max(gap, 0.0), pause_cut)
    return total


def _sentence_features(s: dict, words: list[dict], energy: np.ndarray) -> dict:
    ws = words[s["word_idx"][0]: s["word_idx"][1]]
    dur = max(s["end"] - s["start"], 0.1)
    a, b = int(s["start"] / ENERGY_WINDOW_S), int(s["end"] / ENERGY_WINDOW_S) + 1
    seg_energy = energy[a:b] if len(energy) else np.array([])
    tokens = [_norm(w["word"]) for w in ws]
    opener = " ".join(tokens[:2])
    joined = " ".join(tokens)
    last_word = ws[-1]["word"].rstrip() if ws else ""
    return {
        "conclusive": any(f" {c} " in f" {joined} " for c in CONCLUSIVE),
        "dangling": (any(opener == d or opener.startswith(d + " ") for d in DANGLING_OPENERS)
                     or last_word.endswith((",", ";", ":", "..."))),
        "filler": (any(opener == f or opener.startswith(f + " ") for f in FILLER_OPENERS)
                   or any(t in FILLER_WORDS for t in tokens) or len(tokens) <= 1),
        "rate": len(ws) / dur,  # palavras/s
        "energy": float(seg_energy.mean()) if seg_energy.size else -60.0,
        "hooks": sum(t in HOOK_WORDS for t in tokens),
        "question": s["text"].rstrip().endswith("?"),
        "exclaim": s["text"].rstrip().endswith("!"),
        "numbers": sum(any(c.isdigit() for c in t) for t in tokens),
        "complete": bool(SENTENCE_END.search(ws[-1]["word"])) if ws else False,
    }


def _zscore(values: list[float], min_std: float = 1e-6) -> np.ndarray:
    """z-score com piso no desvio-padrão: diferenças menores que o ruído de medida
    (ex.: 2,52 vs 2,56 palavras/s) não podem virar ±2 desvios e decidir sozinhas."""
    arr = np.array(values, dtype=float)
    if arr.size == 0:
        return arr
    return (arr - arr.mean()) / max(arr.std(), min_std)


def score_sentences(words: list[dict], energy: list[float]):
    """Frases + características + nota de cada uma (relativas ao vídeo inteiro)."""
    sentences = split_sentences(words)
    energy_arr = np.array(energy, dtype=float)
    feats = [_sentence_features(s, words, energy_arr) for s in sentences]
    rate_z = _zscore([f["rate"] for f in feats], min_std=0.15)       # palavras/s
    energy_z = _zscore([f["energy"] for f in feats], min_std=1.5)    # dB
    sent_score = []
    for f, rz, ez in zip(feats, rate_z, energy_z):
        sent_score.append(0.35 * np.clip(rz, -2, 2) + 0.35 * np.clip(ez, -2, 2)
                          + 0.4 * min(f["hooks"], 3) + 0.3 * min(f["numbers"], 2)
                          + 0.4 * f["exclaim"] - 1.0 * f["filler"])
    return sentences, feats, sent_score, energy_z


def select_shorts(words: list[dict], energy: list[float],
                  min_s: float = config.SHORT_MIN_S, max_s: float = config.SHORT_MAX_S,
                  max_shorts: int = config.MAX_SHORTS,
                  target_s: float = config.SHORT_TARGET_S) -> list[dict]:
    if not words:
        return []
    target_s = min(max(target_s, min_s), max_s)
    sentences, feats, sent_score, energy_z = score_sentences(words, energy)
    gaps_before = [0.0] + [b["start"] - a["end"] for a, b in zip(sentences, sentences[1:])]

    sent_dur = [speech_duration(words[s["word_idx"][0]: s["word_idx"][1]]) for s in sentences]

    windows = []
    for i in range(len(sentences)):
        if feats[i]["filler"]:
            continue  # nunca abrir com "bom, então..."
        kept, dur = [], 0.0
        for j in range(i, len(sentences)):
            if sentences[j]["end"] - sentences[i]["start"] > 2 * max_s:
                break
            # Frases de bastidor no meio do trecho são cortadas fora (jump cut)
            if feats[j]["filler"]:
                continue
            dur += sent_dur[j] + (config.PAUSE_CUT_S if kept else 0.0)
            kept.append(j)
            if dur > max_s:
                break
            if dur < min_s:
                continue
            first, last = feats[i], feats[j]
            body = float(np.mean([sent_score[k] for k in kept]))
            hook = (1.0 * min(first["hooks"], 2) + 1.2 * first["question"]
                    + 0.6 * (first["numbers"] > 0) + 0.5 * np.clip(energy_z[i], 0, 2))
            # Final: precisa fechar a ideia; frase pendurada faz o público sair antes
            ending = (0.5 if last["complete"] else -1.0) + 0.6 * last["conclusive"] \
                + 0.3 * last["exclaim"] - 0.8 * last["dangling"]
            # "Rabo fraco": se o melhor já passou, o público sai antes do fim
            tail = float(np.mean([sent_score[k] for k in kept[-2:]]))
            weak_tail = 0.6 * min(0.0, tail - body)
            topic_breaks = sum(gaps_before[k] > TOPIC_GAP_S for k in kept[1:])
            removed = (j - i + 1) - len(kept)
            # Perto do alvo (~38s); passar dele pesa mais que ficar abaixo
            over = max(0.0, dur - target_s)
            under = max(0.0, target_s - dur)
            length = -(1.6 * over + 0.6 * under) / max_s
            windows.append({
                "start": sentences[i]["start"], "end": sentences[j]["end"],
                "kept": list(kept), "speech_duration": round(dur, 2),
                "score_raw": (body + hook + ending + weak_tail + length
                              - 0.5 * topic_breaks - 0.2 * removed),
            })

    # Seleção gulosa sem sobreposição (como NMS)
    windows.sort(key=lambda w: w["score_raw"], reverse=True)
    chosen = []
    for w in windows:
        if all(w["end"] <= c["start"] or w["start"] >= c["end"] for c in chosen):
            chosen.append(w)
        if len(chosen) >= max_shorts:
            break

    if not chosen:
        return []
    raws = [c["score_raw"] for c in windows]
    lo, hi = min(raws), max(raws)
    shorts = []
    for c in sorted(chosen, key=lambda w: w["start"]):
        kept = c["kept"]
        # Junta frases consecutivas mantidas em trechos contínuos do original
        segments = []
        for k in kept:
            s = sentences[k]
            if segments and segments[-1]["last"] == k - 1:
                segments[-1].update(end=s["end"], last=k)
            else:
                segments.append({"start": s["start"], "end": s["end"], "last": k})
        shorts.append({
            "start": c["start"],
            "end": c["end"],
            "segments": [{"start": g["start"], "end": g["end"]} for g in segments],
            "speech_duration": c["speech_duration"],
            "score": int(round(100 * (c["score_raw"] - lo) / (hi - lo))) if hi > lo else 50,
            "title": make_title(sentences[kept[0]]["text"]),
            "text": " ".join(sentences[k]["text"] for k in kept),
        })
    return shorts


def make_title(sentence: str, max_words: int = 8) -> str:
    words = sentence.strip().split()
    title = " ".join(words[:max_words]).rstrip(",;:")
    return title + ("…" if len(words) > max_words else "")
