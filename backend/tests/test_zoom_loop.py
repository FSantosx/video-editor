"""Zoom dinâmico (punch-in alternado) e final em loop."""
import pytest

from app import config
from app.pipeline.captions import build_ass
from app.pipeline.edit import EDGE_PAD_S, build_short, clip_zooms, main_clips, render_clips
from app.pipeline.render import build_command
from app.pipeline.teaser import apply_loop, build_teaser
from test_pipeline import make_words

# ~45s de fala com pausas longas entre frases (cada frase vira um clip)
SCRIPT = [(f"Esta é a frase número {i} da história.", 0.6) for i in range(14)] + [
    ("O maior erro foi confiar nas pesquisas!", 0.6),
    ("Depois disso tudo mudou.", 0.6),
]


@pytest.fixture()
def short():
    words = make_words(SCRIPT)
    cand = {"start": words[0]["start"], "end": words[-1]["end"], "title": "T", "score": 1, "text": ""}
    teaser = build_teaser(words, [], [cand], enabled=True, for_loop=True)
    s = build_short(1, cand, words, teaser=teaser)
    s["zoom"] = {"enabled": True}
    return s


def test_loop_ends_right_before_teaser_sentence(short):
    assert short["teaser"]["text"] == "O maior erro foi confiar nas pesquisas!"
    assert apply_loop(short, True)
    teaser_start = short["teaser"]["clips"][0]["in"]
    main = main_clips(short)
    first_word = teaser_start + EDGE_PAD_S
    assert main[-1]["out"] < first_word  # termina antes da 1ª palavra do teaser
    assert all(c["in"] < first_word for c in main)  # nada depois do teaser
    assert render_clips(short)[0] == short["teaser"]["clips"][0]
    assert abs(short["duration"] - sum(c["out"] - c["in"] for c in render_clips(short))) < 0.01
    assert short["duration"] >= config.LOOP_MIN_S


def test_loop_refused_when_cut_would_be_too_short(short, monkeypatch):
    monkeypatch.setattr(config, "LOOP_MIN_S", 999)
    assert not apply_loop(short, True)
    assert not short["loop"]["enabled"]
    assert main_clips(short) == short["clips"]  # sem loop, trecho inteiro


def test_loop_teaser_comes_from_the_end_so_cut_keeps_min_length():
    # frase forte cedo e outra no fim: no loop, o teaser tem que ser a do fim
    script = [("O maior erro foi confiar nas pesquisas!", 0.6)] + SCRIPT[:12] + [
        ("Nunca mais eu faço isso!", 0.6)]
    words = make_words(script)
    seg = [{"start": words[0]["start"], "end": words[-1]["end"]}]
    assert build_teaser(words, [], seg, for_loop=True)["text"] == "Nunca mais eu faço isso!"


def test_zoom_alternates_and_loop_seam_matches(short):
    apply_loop(short, True)
    zooms = clip_zooms(short)
    n_teaser = len(short["teaser"]["clips"])
    assert zooms[:n_teaser] == [1.0] * n_teaser  # no loop o teaser não tem zoom de "prévia"
    main = zooms[n_teaser:]
    assert main[0] == 1.0 and main[1] == config.ZOOM_PUNCH  # alterna a cada corte
    assert main[-1] == zooms[0]  # emenda do loop: último clip igual ao primeiro


def test_without_loop_teaser_keeps_preview_zoom(short):
    apply_loop(short, False)
    zooms = clip_zooms(short)
    assert zooms[0] == config.TEASER_ZOOM


def test_zoom_off_keeps_main_clips_unzoomed(short):
    apply_loop(short, False)
    short["zoom"] = {"enabled": False}
    n_teaser = len(short["teaser"]["clips"])
    assert set(clip_zooms(short)[n_teaser:]) == {1.0}


def test_render_command_applies_one_zoom_per_clip(short, tmp_path):
    apply_loop(short, True)
    short["reframe"] = {"mode": "crop", "centers": [0.5] * len(render_clips(short))}
    cmd = build_command(tmp_path / "s.mp4", short, {"width": 1920, "height": 1080}, None,
                        tmp_path / "o.mp4")
    graph = cmd[cmd.index("-filter_complex") + 1]
    punch = sum(z > 1.0 for z in clip_zooms(short))
    assert punch > 0 and graph.count("scale=1208:2150,crop=1080:1920:") == punch


def test_cta_moves_to_middle_in_loop():
    ass = build_ass([], None, 0, cta="Comenta aí!", cta_seconds=3.0, total=40.0, cta_middle=True)
    line = next(line for line in ass.splitlines() if "Comenta aí!" in line)
    assert line.startswith("Dialogue: 1,0:00:18.00,0:00:21.00")  # 45% de 40s
    end = build_ass([], None, 0, cta="Comenta aí!", cta_seconds=3.0, total=40.0)
    assert "0:00:37.00,0:00:40.00" in end


def test_numpy_times_from_whisper_do_not_break_json(tmp_path):
    """O faster-whisper pode devolver tempos numpy.float64; o JSON do short precisa gravar."""
    import json

    import numpy as np

    from app import store

    words = [{**w, "start": np.float64(w["start"]), "end": np.float64(w["end"])}
             for w in make_words(SCRIPT)]
    cand = {"start": words[0]["start"], "end": words[-1]["end"], "title": "T", "score": 1, "text": ""}
    s = build_short(1, cand, words, teaser=build_teaser(words, [], [cand], enabled=True))
    assert type(apply_loop(s, True)) is bool
    store._write(tmp_path / "s.json", [s])  # antes: TypeError numpy.bool_
    assert json.loads((tmp_path / "s.json").read_text())[0]["loop"]["enabled"] is True
    # e qualquer numpy que escape também é convertido
    store._write(tmp_path / "n.json", {"b": np.bool_(True), "f": np.float64(1.5), "i": np.int64(2)})
    assert store._read(tmp_path / "n.json") == {"b": True, "f": 1.5, "i": 2}


def _realistic_words(n_sentences=120, seed=1):
    """Fala com pausas reais (hesitações e respiros), como no Whisper de um vídeo de verdade."""
    import random
    rnd = random.Random(seed)
    vocab = ("o problema da campanha foi a gente não ouvir as pessoas na rua e isso custou caro "
             "eu aprendi que dinheiro sozinho não ganha eleição você precisa de verdade").split()
    words, t = [], 0.5
    for _ in range(n_sentences):
        n = rnd.randint(7, 16)
        for k in range(n):
            w = rnd.choice(vocab) + (rnd.choice([".", ".", "!", "?"]) if k == n - 1 else "")
            d = rnd.uniform(0.18, 0.45)
            words.append({"word": w, "start": round(t, 3), "end": round(t + d, 3)})
            t += d + (rnd.uniform(0.3, 0.9) if rnd.random() < 0.18 else rnd.uniform(0.02, 0.12))
        t += rnd.uniform(0.4, 1.4)
    return words


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_loop_engages_on_speech_with_real_pauses(seed):
    """Regressão: o teaser era escolhido no tempo bruto (com pausas) e o loop, verificado no
    tempo editado; em fala real o loop era recusado em ~40% dos cortes, sem aviso."""
    from app.pipeline.select import select_shorts
    words = _realistic_words(seed=seed)
    cands = select_shorts(words, [], target_s=config.SHORT_TARGET_S + 4, max_shorts=8)
    looped = 0
    for c in cands:
        s = build_short(1, c, words, teaser=build_teaser(words, [], c.get("segments") or [c]))
        if apply_loop(s, True):
            looped += 1
            assert s["duration"] >= config.LOOP_MIN_S
        else:
            assert s["loop"]["reason"]  # motivo visível na interface
    assert looped >= 0.85 * len(cands), f"{looped}/{len(cands)}"


def test_loop_teaser_can_be_the_end_of_a_sentence():
    """Corte curto: o teaser vira o final da última frase (o loop completa a frase)."""
    long_last = ("E foi exatamente nesse dia que eu entendi que a campanha inteira "
                 "estava errada desde o começo!")
    words = make_words([(f"Esta é a frase número {i} da história.", 0.6) for i in range(9)]
                       + [(long_last, 0.6)])
    seg = [{"start": words[0]["start"], "end": words[-1]["end"]}]
    teaser = build_teaser(words, [], seg, for_loop=True)
    assert long_last.endswith(teaser["text"]) and teaser["text"] != long_last
