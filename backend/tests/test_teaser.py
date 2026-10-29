"""Abertura com teaser: escolha do momento, montagem e render."""
import subprocess

from app.pipeline.captions import build_ass
from app.pipeline.edit import build_short, map_words_to_output, render_clips
from app.pipeline.render import build_command
from app.pipeline.teaser import pick_teaser
from test_pipeline import make_words

SCRIPT = [
    ("Hoje eu vou contar como foi a minha campanha.", 0.3),
    ("Começou devagar, com pouca gente na rua.", 0.3),
    ("A equipe era pequena e o dinheiro curto.", 0.3),
    ("Fomos visitando bairro por bairro.", 0.3),
    ("O maior erro foi confiar nas pesquisas!", 0.3),
    ("Depois disso a gente mudou a estratégia.", 0.3),
]


def segments_of(words):
    return [{"start": words[0]["start"], "end": words[-1]["end"]}]


def test_picks_strong_sentence_from_later_part():
    words = make_words(SCRIPT)
    teaser = pick_teaser(words, [], segments_of(words))
    assert teaser["text"] == "O maior erro foi confiar nas pesquisas!"


def test_never_picks_from_the_opening():
    # frase forte logo no início: repetir a abertura não serve de teaser
    words = make_words([("O maior erro foi confiar nas pesquisas!", 0.3)] + SCRIPT[1:4])
    teaser = pick_teaser(words, [], segments_of(words))
    assert teaser is None or not teaser["text"].startswith("O maior erro")


def test_long_sentence_is_cut_short_for_curiosity():
    long = ("E foi exatamente nesse momento que eu percebi que tinha perdido "
            "tudo o que tinha construído em dez anos!")
    words = make_words(SCRIPT[:4] + [(long, 0.3)])
    teaser = pick_teaser(words, [], segments_of(words), max_s=3.5)
    assert teaser and teaser["end"] - teaser["start"] <= 3.5
    assert long.startswith(teaser["text"]) and teaser["text"] != long


def _short_with_teaser(words):
    from app.pipeline.teaser import build_teaser
    cand = {"start": words[0]["start"], "end": words[-1]["end"], "title": "T", "score": 1, "text": ""}
    return build_short(1, cand, words, teaser=build_teaser(words, [], segments_of(words), enabled=True))


def test_teaser_goes_first_and_counts_in_duration():
    words = make_words(SCRIPT)
    short = _short_with_teaser(words)
    clips = render_clips(short)
    assert clips[0] == short["teaser"]["clips"][0]
    assert clips[1:] == short["clips"]
    total = sum(c["out"] - c["in"] for c in clips)
    assert abs(short["duration"] - total) < 0.01
    # legendas: as palavras do teaser aparecem no início E de novo no lugar delas
    out = map_words_to_output(words, clips)
    assert out[0]["word"] == "O" and out[0]["start"] < 0.2
    assert sum(w["word"] == "pesquisas!" for w in out) == 2
    assert "PESQUISAS" in build_ass(out, None, 0)


def test_teaser_rendered_with_zoom(tmp_path):
    words = make_words(SCRIPT)
    short = _short_with_teaser(words)
    short["reframe"] = {"mode": "crop", "centers": [0.5] * len(render_clips(short))}
    cmd = build_command(tmp_path / "src.mp4", short, {"width": 1920, "height": 1080}, None,
                        tmp_path / "out.mp4")
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert graph.count("scale=1166:2072,crop=1080:1920") == len(short["teaser"]["clips"])
    assert graph.count("-i") == 0 and cmd.count("-i") == len(render_clips(short))
