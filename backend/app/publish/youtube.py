"""Integração com a API do YouTube: login (OAuth 2.0) e upload com publicação programada.

Fluxo de login: /youtube/connect devolve a URL do Google; o usuário autoriza e o Google
volta em /youtube/callback, que troca o código pelo token (guardado em DATA_DIR, com o
refresh token para não precisar logar de novo).

Atenção: projetos da API não auditados pelo Google só conseguem enviar vídeos PRIVADOS,
e o publishAt não tem efeito. Por isso o envio automático só acontece com
YOUTUBE_AUDITED=1; antes disso, só o envio de teste (privado), manual.
"""
import json
import logging
import secrets
import time

from .. import config

log = logging.getLogger("youtube")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]
STATE_TTL_S = 15 * 60


class YouTubeError(RuntimeError):
    pass


def configured() -> bool:
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET and config.PUBLIC_URL)


def redirect_uri() -> str:
    return f"{config.PUBLIC_URL}/youtube/callback"


def _token_path():
    return config.DATA_DIR / "youtube_token.json"


def _states_path():
    return config.DATA_DIR / "youtube_oauth_states.json"


def _client_config() -> dict:
    return {"web": {
        "client_id": config.GOOGLE_CLIENT_ID,
        "client_secret": config.GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [redirect_uri()],
    }}


def _flow(state: str | None = None):
    from google_auth_oauthlib.flow import Flow

    return Flow.from_client_config(_client_config(), scopes=SCOPES, state=state,
                                   redirect_uri=redirect_uri())


# ---------------------------------------------------------------- login

def start_auth() -> str:
    """URL de autorização do Google. Guarda state + code_verifier (PKCE) para o retorno."""
    if not configured():
        raise YouTubeError("defina GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET e PUBLIC_URL")
    state = secrets.token_urlsafe(24)
    flow = _flow(state)
    url, _ = flow.authorization_url(access_type="offline", prompt="consent",
                                    include_granted_scopes="true", state=state)
    states = _read_json(_states_path(), {})
    now = time.time()
    states = {k: v for k, v in states.items() if now - v["at"] < STATE_TTL_S}
    states[state] = {"at": now, "verifier": getattr(flow, "code_verifier", None)}
    _write_json(_states_path(), states)
    return url


def finish_auth(state: str, code: str) -> dict:
    states = _read_json(_states_path(), {})
    pending = states.pop(state, None)
    _write_json(_states_path(), states)
    if not pending or time.time() - pending["at"] > STATE_TTL_S:
        raise YouTubeError("login expirado ou inválido; tente conectar de novo")
    flow = _flow(state)
    if pending.get("verifier"):
        flow.code_verifier = pending["verifier"]
    flow.fetch_token(code=code)
    creds = flow.credentials
    if not creds.refresh_token:
        raise YouTubeError("o Google não devolveu o refresh token; remova o acesso do app "
                           "em myaccount.google.com/permissions e conecte de novo")
    _write_json(_token_path(), json.loads(creds.to_json()))
    info = channel_info(force=True)
    log.info("YouTube conectado: %s", info.get("title"))
    return info


def disconnect() -> None:
    for p in (_token_path(), config.DATA_DIR / "youtube_channel.json"):
        p.unlink(missing_ok=True)


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    data = _read_json(_token_path(), None)
    if not data:
        raise YouTubeError("YouTube não conectado")
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if not creds.valid:
        creds.refresh(Request())
        _write_json(_token_path(), json.loads(creds.to_json()))
    return creds


def _service():
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=_credentials(), cache_discovery=False)


def channel_info(force: bool = False) -> dict:
    cache = config.DATA_DIR / "youtube_channel.json"
    if not force and (cached := _read_json(cache, None)):
        return cached
    resp = _service().channels().list(part="snippet", mine=True).execute()
    items = resp.get("items") or []
    info = {"id": items[0]["id"], "title": items[0]["snippet"]["title"]} if items else {}
    _write_json(cache, info)
    return info


def status() -> dict:
    connected = _token_path().exists()
    channel = None
    if connected:
        try:
            channel = channel_info()
        except Exception as exc:  # token revogado etc.: mostra como desconectado
            log.warning("falha ao ler o canal: %s", exc)
            connected = False
    return {"configured": configured(), "connected": connected, "channel": channel,
            "audited": config.YOUTUBE_AUDITED,
            "auto_upload": connected and config.YOUTUBE_AUDITED}


# ---------------------------------------------------------------- upload

def upload(path, title: str, description: str, tags: list[str], publish_at: str | None,
           on_progress=None) -> str:
    """Envia o MP4. Com publish_at, fica privado até o horário e o YouTube publica sozinho.

    Retorna o id do vídeo no YouTube.
    """
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    status_body = {"privacyStatus": "private", "selfDeclaredMadeForKids": False}
    if publish_at:
        status_body["publishAt"] = publish_at  # só vale com privacyStatus=private
    body = {
        "snippet": {"title": title, "description": description, "tags": tags,
                    "categoryId": config.YOUTUBE_CATEGORY_ID, "defaultLanguage": "pt-BR"},
        "status": status_body,
    }
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024,
                            resumable=True)
    try:
        request = _service().videos().insert(part="snippet,status", body=body,
                                             media_body=media)
        response = None
        while response is None:
            progress, response = request.next_chunk(num_retries=3)
            if progress and on_progress:
                on_progress(progress.progress())
    except HttpError as exc:
        reason = ""
        try:
            reason = json.loads(exc.content)["error"]["errors"][0]["reason"]
        except Exception:
            pass
        if reason in ("quotaExceeded", "uploadLimitExceeded"):
            raise YouTubeError("limite diário de envios do YouTube atingido; tente amanhã")
        raise YouTubeError(f"YouTube recusou o envio ({exc.status_code} {reason})".strip())
    return response["id"]


# ---------------------------------------------------------------- util

def _read_json(path, default):
    from .. import store

    return store._read(path, default)


def _write_json(path, data) -> None:
    from .. import store

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    store._write(path, data)
