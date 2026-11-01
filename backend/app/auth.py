"""API key (header X-API-Key ou ?key=) compartilhada pelas rotas."""
import secrets

from fastapi import HTTPException, Request

from . import config


def require_key(request: Request) -> None:
    if not config.API_KEY:
        return
    key = request.headers.get("x-api-key") or request.query_params.get("key") or ""
    if not secrets.compare_digest(key, config.API_KEY):
        raise HTTPException(401, "API key inválida")
