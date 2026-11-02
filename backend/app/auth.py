"""Autenticação das rotas: a chave (header X-API-Key ou ?key=) identifica a conta."""
from fastapi import Request

from .accounts import current_user


def require_key(request: Request) -> None:
    """Para rotas que não dependem da conta (ex.: /system): só exige uma chave válida."""
    current_user(request)
