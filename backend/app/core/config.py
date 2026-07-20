from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


def _json_dict(name: str) -> dict[str, str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{name} contém JSON inválido") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{name} deve conter um objeto JSON")
    return {str(key): str(item) for key, item in value.items()}


@dataclass(frozen=True)
class Settings:
    environment: str
    session_secret: str
    session_ttl_seconds: int
    cookie_secure: bool
    admin_password_hash: str
    admin_password: str
    professor_password_hashes: dict[str, str]
    professor_passwords: dict[str, str]
    cors_origins: tuple[str, ...]
    frontend_dist: Path

    @property
    def production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = os.environ.get("APP_ENV", "development").strip()
    secret = os.environ.get("SESSION_SECRET", "").strip()
    if not secret and environment.lower() == "production":
        raise RuntimeError("SESSION_SECRET é obrigatória em produção")
    raw_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
    frontend_dist = Path(os.environ.get("FRONTEND_DIST", "frontend/dist"))
    if not frontend_dist.is_absolute():
        frontend_dist = PROJECT_ROOT / frontend_dist
    return Settings(
        environment=environment,
        session_secret=secret or "dev-only-change-me",
        session_ttl_seconds=int(os.environ.get("SESSION_TTL_SECONDS", "43200")),
        cookie_secure=os.environ.get("COOKIE_SECURE", "").lower()
        in {"1", "true", "yes", "sim"} or environment.lower() == "production",
        admin_password_hash=os.environ.get("APP_PASSWORD_HASH", "").strip(),
        admin_password=os.environ.get("APP_PASSWORD", "").strip(),
        professor_password_hashes=_json_dict("PROFESSOR_PASSWORD_HASHES_JSON"),
        professor_passwords=_json_dict("PROFESSOR_PASSWORDS_JSON"),
        cors_origins=tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip()),
        frontend_dist=frontend_dist,
    )
