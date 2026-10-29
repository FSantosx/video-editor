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


def test_prefers_target_length_over_max():
    """Feedback do YouTube: 55s reteve 48,8%. Com material de sobra, mirar ~38s, não 60s."""
    script = [(f"Você sabia que o erro número {i} custa dinheiro de verdade?", 0.3) for i in range(40)]
    shorts = select_shorts(make_words(script), energy=[], min_s=30, max_s=60, max_shorts=3,
                           target_s=38)
    assert shorts
    assert all(s["speech_duration"] <= 45 for s in shorts), [s["speech_duration"] for s in shorts]


def test_prefers_conclusive_ending_over_dangling():
    intro = [(f"Você sabia que o erro número {i} custa caro?", 0.3) for i in range(9)]
    conclusive = intro + [("Por isso a lição é anotar tudo!", 0.3),
                          ("Mas aí eu fui ver outra coisa,", 0.3),
                          ("e depois a gente conversa sobre", 1.5)]
    shorts = select_shorts(make_words(conclusive), energy=[], min_s=10, max_s=60, max_shorts=1,
                           target_s=20)
    assert shorts[0]["text"].rstrip().endswith("anotar tudo!")


def test_cta_shown_at_end_without_overlapping_title():
    words = [{"word": "fala", "start": 0.0, "end": 0.4}]
    ass = build_ass(words, "Título", 3.0, cta="Comenta aí!", cta_seconds=3.0, total=20.0)
    cta_line = next(line for line in ass.splitlines() if "Comenta aí!" in line)
    assert cta_line.startswith("Dialogue: 1,0:00:17.00,0:00:20.00,Title")
    # vídeo curto: a chamada não pode começar antes do título acabar
    short = build_ass(words, "Título", 3.0, cta="Comenta aí!", cta_seconds=3.0, total=4.5)
    assert "0:00:03.00,0:00:04.50" in short
    assert "Comenta" not in build_ass(words, "T", 3.0, cta="Comenta aí!", total=3.5)


def test_store_retries_when_windows_locks_the_file(tmp_path, monkeypatch):
    """Windows: ler/substituir um arquivo aberto por outro dá PermissionError; deve tentar de novo."""
    from pathlib import Path

    from app import store
    path = tmp_path / "x.json"
    store._write(path, {"a": 1})

    calls = {"n": 0}
    real_read = Path.read_text

    def flaky_read(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 3:
            raise PermissionError(13, "Permission denied")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(store, "RETRY_WAIT_S", 0)
    monkeypatch.setattr(Path, "read_text", flaky_read)
    assert store._read(path) == {"a": 1} and calls["n"] == 4

    real_replace = store.os.replace
    fails = {"n": 0}

    def flaky_replace(src, dst):
        fails["n"] += 1
        if fails["n"] <= 2:
            raise PermissionError(13, "Permission denied")
        return real_replace(src, dst)

    monkeypatch.setattr(Path, "read_text", real_read)
    monkeypatch.setattr(store.os, "replace", flaky_replace)
    store._write(path, {"a": 2})
    assert store._read(path) == {"a": 2}
