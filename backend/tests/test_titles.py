"""Título de gancho: heurística, caminho do Claude (cliente falso) e fallback."""
import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app import config
from app.pipeline import titles
from app.pipeline.captions import build_ass

ITEMS = [
    {"text": "Hoje eu vou contar como foi a campanha. O maior erro foi confiar nas pesquisas!",
     "teaser": "O maior erro foi confiar nas pesquisas!"},
    {"text": "No fim do mês você vai ver para onde o dinheiro está indo.", "teaser": None},
]


@pytest.mark.parametrize("text, expected", [
    ("O maior erro foi confiar nas pesquisas!", "O MAIOR ERRO FOI CONFIAR"),  # 7 palavras → 6, sem "NAS"
    ("Eu perdi dez mil reais em um ano", "DEZ MIL REAIS EM UM ANO"),  # começa no número
    ("Ninguém te conta isso.", "NINGUÉM TE CONTA ISSO"),
    ("Por que você nunca consegue sair das dívidas?", "VOCÊ NUNCA CONSEGUE SAIR"),
])
def test_heuristic_hook(text, expected):
    hook = titles.heuristic_hook(text)
    assert hook.startswith(expected) or hook == expected, hook
    assert len(hook.split()) <= titles.HOOK_MAX_WORDS and len(hook) <= titles.HOOK_MAX_CHARS
    assert not hook.split()[-1].lower() in titles.TRAILING_STOP


def test_without_key_uses_heuristic(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(config, "TITLES_ENGINE", "auto")
    out = titles.generate_titles(ITEMS, context="Renan entrevista")
    assert [o["source"] for o in out] == ["heuristic", "heuristic"]
    # não repete a frase do teaser (já está sendo falada e legendada)
    assert "PESQUISAS" not in out[0]["hook"]
    assert out[1]["hook"] == "VOCÊ VAI VER"


def test_hook_source_skips_teaser_and_prefers_hook_words():
    text = ("Hoje é segunda. Você sabia que o maior erro é não anotar nada? "
            "No fim do mês você vai ver tudo.")
    assert titles.hook_source(text, "No fim do mês você vai ver tudo.").startswith("Você sabia")
    assert titles.heuristic_hook(titles.hook_source(text, None)) == "VOCÊ SABIA QUE O MAIOR ERRO"


class FakeClient:
    """Imita anthropic.Anthropic().beta.messages.create."""

    def __init__(self, response=None, error=None):
        self.calls = []
        self._response, self._error = response, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response


def fake_response(payload, stop_reason="end_turn"):
    block = SimpleNamespace(type="text", text=json.dumps(payload))
    thinking = SimpleNamespace(type="thinking", thinking="")
    return SimpleNamespace(content=[thinking, block], stop_reason=stop_reason, _request_id="req_x")


@pytest.fixture()
def with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(config, "TITLES_ENGINE", "auto")
    monkeypatch.setattr(config, "CLAUDE_MODEL", "claude-opus-5-5")

    def install(client):
        monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: client)
        return client
    return install


def test_llm_titles_used_and_request_shape(with_key):
    client = with_key(FakeClient(fake_response({"shorts": [
        {"index": 1, "hook": "pra onde vai seu dinheiro?", "title": "O teste do mês que muda tudo"},
        {"index": 0, "hook": "\"O erro que custou a eleição\"", "title": "Renan admite o maior erro"},
    ]})))
    out = titles.generate_titles(ITEMS, context="Renan entrevista")
    assert out[0] == {"hook": "O ERRO QUE CUSTOU A ELEIÇÃO", "title": "Renan admite o maior erro",
                      "source": "llm"}
    assert out[1]["hook"] == "PRA ONDE VAI SEU DINHEIRO?"

    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in call and "temperature" not in call
    prompt = call["messages"][0]["content"]
    assert "Renan entrevista" in prompt and '<corte index="1">' in prompt
    assert "<momento_mais_forte>O maior erro" in prompt


def test_model_without_server_fallback_omits_it(with_key, monkeypatch):
    monkeypatch.setattr(config, "CLAUDE_MODEL", "claude-haiku-5-5")
    client = with_key(FakeClient(fake_response({"shorts": []})))
    titles.generate_titles(ITEMS)
    assert "fallbacks" not in client.calls[0] and "betas" not in client.calls[0]


def test_missing_item_falls_back_individually(with_key):
    with_key(FakeClient(fake_response({"shorts": [{"index": 0, "hook": "GANCHO", "title": "T"}]})))
    out = titles.generate_titles(ITEMS)
    assert [o["source"] for o in out] == ["llm", "heuristic"]


@pytest.mark.parametrize("client", [
    FakeClient(fake_response({"shorts": []}, stop_reason="refusal")),
    FakeClient(error=anthropic.APIConnectionError(request=httpx.Request("POST", "https://x"))),
    FakeClient(error=anthropic.RateLimitError(
        "limite", response=httpx.Response(429, request=httpx.Request("POST", "https://x")), body=None)),
    FakeClient(error=anthropic.AuthenticationError(
        "chave", response=httpx.Response(401, request=httpx.Request("POST", "https://x")), body=None)),
])
def test_api_problems_never_break_the_pipeline(with_key, client):
    with_key(client)
    out = titles.generate_titles(ITEMS)
    assert [o["source"] for o in out] == ["heuristic", "heuristic"]


def test_hook_overlay_replaces_title_and_pops_in():
    ass = build_ass([], "Título longo do post", 3.0, hook="O ERRO QUE CUSTOU A ELEIÇÃO",
                    cta="Comenta aí!", total=20.0)
    hook_line = next(line for line in ass.splitlines() if "O ERRO QUE CUSTOU" in line)
    assert hook_line.startswith("Dialogue: 2,0:00:00.00,0:00:03.00,Hook")
    assert "\\fad(0," in hook_line  # aparece já no primeiro frame
    assert "Título longo do post" not in ass
    assert "0:00:17.00,0:00:20.00" in ass  # chamada no fim continua
