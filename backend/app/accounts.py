"""Contas: cada pessoa tem a própria chave de acesso e vê só os próprios dados.

- A API_KEY do servidor continua valendo: é a conta **principal** (administrador). Dados
  criados antes das contas (sem "owner") pertencem a ela.
- O administrador cria contas (POST /admin/users); cada uma recebe uma chave própria, que a
  pessoa coloca no campo "API key" do app. Guardamos só o hash da chave.
- Sem API_KEY (PC/modo local), tudo é da conta principal, sem senha, como antes.

Separado por conta: vídeos e cortes, agenda de publicação, horários e canal do YouTube.
"""
import hashlib
import hmac
import secrets
import shutil
import time
from pathlib import Path

from fastapi import Depends, HTTPException, Request

from . import config, store

PRINCIPAL_ID = "principal"
PRINCIPAL = {"id": PRINCIPAL_ID, "name": "Principal", "admin": True}


def _users_path() -> Path:
    return config.DATA_DIR / "users.json"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _public(user: dict) -> dict:
    return {k: v for k, v in user.items() if k != "token_hash"}


def list_users() -> list[dict]:
    return store._read(_users_path(), [])


def create_user(name: str) -> tuple[dict, str]:
    """Cria a conta e devolve (conta, chave). A chave só aparece aqui; depois, só o hash."""
    token = secrets.token_urlsafe(24)
    user = {"id": "u" + secrets.token_hex(5), "name": name.strip(), "admin": False,
            "created_at": time.time(), "token_hash": _hash(token)}
    with store._lock:
        users = list_users()
        if any(u["name"].lower() == user["name"].lower() for u in users):
            raise ValueError("já existe uma conta com esse nome")
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        store._write(_users_path(), users + [user])
    return _public(user), token


def rotate_token(user_id: str) -> str:
    token = secrets.token_urlsafe(24)
    with store._lock:
        users = list_users()
        for u in users:
            if u["id"] == user_id:
                u["token_hash"] = _hash(token)
                store._write(_users_path(), users)
                return token
    raise KeyError(user_id)


def delete_user(user_id: str, purge: bool = False) -> None:
    """Revoga a conta. Com purge, apaga também vídeos, agenda e canal dela."""
    with store._lock:
        users = list_users()
        kept = [u for u in users if u["id"] != user_id]
        if len(kept) == len(users):
            raise KeyError(user_id)
        store._write(_users_path(), kept)
    if purge:
        for v in store.list_videos(owner=user_id):
            store.delete_video(v["id"])
        from .publish import queue
        queue.delete_owner_items(user_id)
        shutil.rmtree(user_dir(user_id), ignore_errors=True)


def user_dir(owner: str) -> Path:
    if not owner.isalnum():
        raise KeyError(owner)
    return config.DATA_DIR / "users" / owner


def user_file(owner: str, name: str) -> Path:
    """Arquivo da conta (agenda, canal...). A principal usa os arquivos antigos da raiz,
    se existirem, para não perder o que já estava configurado antes das contas."""
    path = user_dir(owner) / name
    legacy = config.DATA_DIR / name
    if owner == PRINCIPAL_ID and not path.exists() and legacy.exists():
        return legacy
    return path


# ---------------------------------------------------------------- dependências do FastAPI

def current_user(request: Request) -> dict:
    if not config.API_KEY:  # modo local (PC): uma pessoa só, sem senha
        return PRINCIPAL
    key = request.headers.get("x-api-key") or request.query_params.get("key") or ""
    if key and hmac.compare_digest(key, config.API_KEY):
        return PRINCIPAL
    if key:
        digest = _hash(key)
        for u in list_users():
            if hmac.compare_digest(u["token_hash"], digest):
                return _public(u)
    raise HTTPException(401, "chave de acesso inválida")


def require_admin(user: dict = Depends(current_user)) -> dict:
    if not user.get("admin"):
        raise HTTPException(403, "só o administrador pode fazer isso")
    return user


def owns(user: dict, record: dict) -> bool:
    return record.get("owner", PRINCIPAL_ID) == user["id"]
