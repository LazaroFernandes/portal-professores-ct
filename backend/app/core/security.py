from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from .config import get_settings


COOKIE_NAME = "nextfit_portal_session"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P
    )
    return "scrypt$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    if not encoded.startswith("scrypt$"):
        return False
    try:
        _, raw_salt, raw_digest = encoded.split("$", 2)
        salt = base64.urlsafe_b64decode(raw_salt)
        expected = base64.urlsafe_b64decode(raw_digest)
    except (ValueError, TypeError):
        return False
    actual = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P
    )
    return hmac.compare_digest(actual, expected)


def authenticate(password: str) -> dict[str, str] | None:
    settings = get_settings()
    if settings.admin_password_hash and verify_password(password, settings.admin_password_hash):
        return {"role": "admin", "name": "Administrador"}
    if settings.admin_password and secrets.compare_digest(password, settings.admin_password):
        return {"role": "admin", "name": "Administrador"}
    for name, encoded in settings.professor_password_hashes.items():
        if verify_password(password, encoded):
            return {"role": "professor", "name": name}
    for name, configured in settings.professor_passwords.items():
        if configured and secrets.compare_digest(password, configured):
            return {"role": "professor", "name": name}
    return None


def create_session(user: dict[str, str]) -> tuple[str, str]:
    settings = get_settings()
    csrf = secrets.token_urlsafe(24)
    payload = {
        "role": user["role"],
        "name": user["name"],
        "csrf": csrf,
        "expires": int(time.time()) + settings.session_ttl_seconds,
    }
    body = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}", csrf


def read_session(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    body, signature = token.rsplit(".", 1)
    expected = hmac.new(
        get_settings().session_secret.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("expires", 0)) < int(time.time()):
        return None
    return payload


def current_user(request: Request) -> dict[str, Any]:
    user = read_session(request.cookies.get(COOKIE_NAME))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada")
    return user


def require_admin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso administrativo necessário")
    return user


def require_csrf(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or not hmac.compare_digest(supplied, str(user.get("csrf", ""))):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token CSRF inválido")
    return user
