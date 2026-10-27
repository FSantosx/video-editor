from app.pipeline.captions import build_ass
from app.pipeline.edit import build_clips, build_short, map_words_to_output
from app.pipeline.select import select_shorts, split_sentences, speech_duration


def make_words(sentences: list[tuple[str, float]], rate: float = 2.5) -> list[dict]:
    """Cria palavras com tempos sintéticos; cada frase seguida de (pausa em s)."""
    words, t = [], 0.0
    for text, pause in sentences:
        for tok in text.split():
            words.append({"word": tok, "start": round(t, 3), "end": round(t + 1 / rate - 0.05, 3)})
            t += 1 / rate
        t += pause
    return words


def test_split_sentences_on_punctuation_and_gaps():
    words = make_words([("Olá pessoal.", 0.2), ("Tudo bem", 1.5), ("aqui é outra frase!", 0)])
    sentences = split_sentences(words)
    assert [s["text"] for s in sentences] == ["Olá pessoal.", "Tudo bem", "aqui é outra frase!"]


def test_build_clips_removes_long_pauses_and_fillers():
    words = make_words([("primeira parte.", 2.0), ("hum", 0.1), ("segunda parte.", 0)])
    clips = build_clips(words, pause_cut=0.35)
    assert len(clips) == 2
    kept = map_words_to_output(words, clips)
    assert [w["word"] for w in kept] == ["primeira", "parte.", "segunda", "parte."]
    # na saída não sobra a pausa de 2s
    assert kept[2]["start"] - kept[1]["end"] < 0.5


def test_select_respects_duration_and_skips_filler_sentences():
    script = []
    for i in range(30):
        if i % 6 == 5:
            script.append(("Bom, deixa eu ajustar a câmera aqui.", 1.5))
        else:
            script.append((f"Você sabia que o erro número {i} custa dinheiro de verdade?", 0.4))
    words = make_words(script)
    shorts = select_shorts(words, energy=[], min_s=30, max_s=60, max_shorts=3)
    assert shorts
    for s in shorts:
        assert 30 <= s["speech_duration"] <= 60
        assert "câmera" not in s["text"]
        assert not s["title"].lower().startswith("bom")
        short = build_short(1, s, words)
        assert 25 <= short["duration"] <= 62
    spans = sorted((s["start"], s["end"]) for s in shorts)
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))  # sem sobreposição


def test_speech_duration_caps_pauses():
    words = make_words([("a b c", 5.0), ("d e f", 0)])
    assert speech_duration(words, pause_cut=0.3) < 3.0


def test_ass_escapes_and_highlights():
    words = [{"word": "olá{x}", "start": 0.0, "end": 0.4}, {"word": "mundo.", "start": 0.5, "end": 0.9}]
    ass = build_ass(words, "Título {com} chaves", 3.0)
    assert "{x}" not in ass and "{com}" not in ass
    assert ass.count("Dialogue: 0,") == 2  # uma linha por palavra destacada
    assert "OLÁX" in ass and "MUNDO" in ass
    assert "Dialogue: 1," in ass  # título
