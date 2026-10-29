"""Título de gancho (texto curto na tela) e título do post para cada corte.

Com ANTHROPIC_API_KEY (ou ANTHROPIC_AUTH_TOKEN) definida, o Claude escreve os
títulos de todos os cortes do vídeo numa única chamada, com saída JSON
estruturada. Sem chave, ou se a API falhar ou recusar, uma heurística monta o
gancho a partir da frase mais forte (a do teaser). O processamento nunca para
por causa dos títulos.

    generate_titles([{"text": ..., "teaser": ...}, ...], context="nome do vídeo")
      -> [{"hook": "O MAIOR ERRO DA CAMPANHA", "title": "...", "source": "llm"}, ...]
"""
import json
import logging
import os
import re

from .. import config
from .select import HOOK_WORDS, _norm, make_title

log = logging.getLogger("titles")

HOOK_MAX_WORDS = 6
HOOK_MAX_CHARS = 42
TITLE_MAX_CHARS = 90
SNIPPET_MAX_CHARS = 1500  # texto de cada corte enviado ao modelo
# Modelos que aceitam o fallback de recusa no servidor (fallbacks: "default")
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

ARTICLES = {"o", "a", "os", "as", "um", "uma", "meu", "minha", "seu", "sua", "esse", "essa",
            "este", "esta", "nosso", "nossa"}
# Adjetivos que costumam vir antes da palavra-gancho ("o MAIOR erro", "a ÚNICA vez")
INTENSIFIERS = {"maior", "menor", "primeiro", "primeira", "ultimo", "ultima", "unico", "unica",
                "grande", "verdadeiro", "verdadeira", "pior", "melhor", "real"}
NUMBER_WORDS = {"dois", "duas", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez",
                "vinte", "trinta", "cem", "cento", "mil", "milhao", "milhoes", "bilhao",
                "bilhoes", "metade", "dobro"}
TRAILING_STOP = ARTICLES | {"de", "do", "da", "dos", "das", "que", "e", "com", "em", "no", "na",
                            "nos", "nas", "para", "pra", "por", "pelo", "pela", "ao", "onde",
                            "mas", "se", "ou", "como", "quando", "foi", "vai", "ser", "eu"}

SYSTEM = """Você é editor-chefe de um canal de cortes em vídeos curtos (YouTube Shorts, Reels, TikTok), \
em português do Brasil. Para cada corte, escreva:

- hook: texto que aparece na tela nos primeiros segundos, sobre o vídeo. No máximo 6 palavras e \
42 caracteres. Precisa fazer a pessoa parar de deslizar: uma afirmação forte, uma revelação, um \
número, uma contradição ou uma pergunta que o próprio corte responde. Sem emojis, sem hashtags, \
sem aspas.
- title: título do post no YouTube, até 70 caracteres. Específico (quem, o quê), com curiosidade, \
sem caixa alta inteira, sem emojis e sem hashtags.

Seja fiel ao que é dito no trecho: não invente fatos, números ou nomes que não estejam no texto \
ou no contexto, e não prometa algo que o corte não entrega. Se o contexto disser quem fala, use o \
nome quando ajudar."""

SCHEMA = {
    "type": "object",
    "properties": {
        "shorts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "hook": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["index", "hook", "title"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["shorts"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------- heurística

def heuristic_hook(text: str) -> str:
    """Gancho curto em maiúsculas a partir de uma frase.

    Frase curta (até 6 palavras) entra inteira; senão, começa na primeira palavra
    de gancho (com o artigo antes dela, ex.: "O MAIOR ERRO...") e corta em 6 palavras,
    sem terminar em preposição/artigo.
    """
    tokens = text.split()
    if not tokens:
        return ""
    norms = [_norm(t) for t in tokens]
    if len(tokens) > HOOK_MAX_WORDS:
        start = 0
        for i, n in enumerate(norms):
            if (n in HOOK_WORDS or n in INTENSIFIERS or n in NUMBER_WORDS
                    or any(c.isdigit() for c in n)):
                start = i
                # inclui adjetivo e artigo antes: "O MAIOR ERRO", "OS DEZ MIL"
                while start > 0 and i - start < 2 and norms[start - 1] in (ARTICLES | INTENSIFIERS):
                    start -= 1
                break
        tokens = tokens[start:]
        norms = norms[start:]
        # termina numa pontuação forte se ela vier cedo o bastante
        for i, t in enumerate(tokens[:HOOK_MAX_WORDS]):
            if i >= 2 and re.search(r"[.!?…]$", t):
                tokens, norms = tokens[: i + 1], norms[: i + 1]
                break
        tokens, norms = tokens[:HOOK_MAX_WORDS], norms[:HOOK_MAX_WORDS]
    while len(tokens) > 2 and norms[-1] in TRAILING_STOP:
        tokens, norms = tokens[:-1], norms[:-1]
    hook = " ".join(tokens)
    hook = re.sub(r"[,;:.…\"“”()]+$", "", hook)  # mantém ? e ! no fim
    hook = re.sub(r"[,;:\"“”()]", "", hook)
    return _fit(hook.upper(), HOOK_MAX_CHARS)


def _fit(text: str, max_chars: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def _has_hook_word(sentence: str) -> bool:
    return any(n in HOOK_WORDS or n in INTENSIFIERS or n in NUMBER_WORDS
               or any(c.isdigit() for c in n) for n in map(_norm, sentence.split()))


def hook_source(text: str, teaser: str | None) -> str:
    """Frase de onde sai o gancho: uma das 3 primeiras com palavra de gancho ou número.

    Evita a frase do teaser: ela já está sendo falada (e legendada) enquanto o
    gancho aparece, e repetir o mesmo texto em dois lugares desperdiça o topo da tela.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    if teaser:
        sentences = [s for s in sentences if teaser.strip() not in s and s not in teaser]
    for s in sentences[:3]:
        if _has_hook_word(s):
            return s
    return sentences[0] if sentences else (teaser or text)


def _heuristic(item: dict) -> dict:
    source = hook_source(item["text"], item.get("teaser"))
    return {"hook": heuristic_hook(source) or heuristic_hook(item["text"]),
            "title": _fit(make_title(item["text"], max_words=12), TITLE_MAX_CHARS),
            "source": "heuristic"}


# ---------------------------------------------------------------- LLM

def llm_available() -> bool:
    if config.TITLES_ENGINE == "heuristic":
        return False
    has_key = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))
    return has_key or config.TITLES_ENGINE == "llm"


def _build_prompt(items: list[dict], context: str | None) -> str:
    parts = []
    if context:
        parts.append(f"Contexto do vídeo original: {context}\n")
    parts.append(f"Escreva hook e title para cada um dos {len(items)} cortes abaixo. "
                 "Responda com um item por corte, usando o mesmo index.\n")
    for i, item in enumerate(items):
        text = item["text"][:SNIPPET_MAX_CHARS]
        block = f'<corte index="{i}">\n<transcricao>{text}</transcricao>'
        if item.get("teaser"):
            block += f"\n<momento_mais_forte>{item['teaser']}</momento_mais_forte>"
        parts.append(block + "\n</corte>")
    return "\n".join(parts)


def _llm_titles(items: list[dict], context: str | None) -> list[dict | None]:
    import anthropic

    client = anthropic.Anthropic(timeout=90.0, max_retries=2)
    extra = {}
    if config.CLAUDE_MODEL in FALLBACK_MODELS:
        # Fallback de recusa no servidor: se o modelo recusar, outro modelo responde
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    response = client.beta.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": _build_prompt(items, context)}],
        output_config={"effort": config.CLAUDE_EFFORT,
                       "format": {"type": "json_schema", "schema": SCHEMA}},
        **extra,
    )
    if response.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"resposta incompleta (stop_reason={response.stop_reason})")
    text = next(b.text for b in response.content if b.type == "text")
    by_index = {s["index"]: s for s in json.loads(text)["shorts"]}
    out: list[dict | None] = []
    for i in range(len(items)):
        s = by_index.get(i)
        hook = _fit(" ".join(s["hook"].split()).strip("\"“” "), HOOK_MAX_CHARS) if s else ""
        title = _fit(s["title"].strip("\"“” "), TITLE_MAX_CHARS) if s else ""
        out.append({"hook": hook.upper(), "title": title, "source": "llm"}
                   if hook and title else None)
    log.info("títulos gerados pelo %s (%d cortes, request %s)",
             config.CLAUDE_MODEL, len(items), response._request_id)
    return out


def generate_titles(items: list[dict], context: str | None = None) -> list[dict]:
    """items: [{"text": transcrição do corte, "teaser": frase do teaser ou None}, ...]"""
    if not items:
        return []
    results: list[dict | None] = [None] * len(items)
    if llm_available():
        import anthropic

        try:
            results = _llm_titles(items, context)
        except anthropic.RateLimitError:
            log.warning("limite de uso da API do Claude; usando títulos heurísticos")
        except anthropic.APIStatusError as exc:
            log.warning("API do Claude respondeu %s; usando títulos heurísticos", exc.status_code)
        except anthropic.APIConnectionError:
            log.warning("sem conexão com a API do Claude; usando títulos heurísticos")
        except (RuntimeError, ValueError, KeyError, StopIteration) as exc:
            log.warning("resposta inesperada do Claude (%s); usando títulos heurísticos", exc)
    return [r or _heuristic(item) for r, item in zip(results, items)]
