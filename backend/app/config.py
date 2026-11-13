from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass

log = logging.getLogger(__name__)


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    secret_key: str
    max_upload_bytes: int = 2 * 1024 * 1024
    max_content_bytes: int = 1 * 1024 * 1024
    seed_demo_users: bool = True
    seed_sample_content: bool = True
    cookie_secure: bool = False
    static_dir: str | None = None
    session_max_age_seconds: int = 7 * 24 * 3600

    @classmethod
    def from_env(cls) -> Settings:
        secret = os.environ.get("SECRET_KEY")
        if not secret:
            secret = secrets.token_urlsafe(32)
            log.warning("SECRET_KEY not set; generated an ephemeral key (sessions reset on restart).")
        return cls(
            database_url=os.environ.get("DATABASE_URL", "sqlite:///./data/ajaia.db"),
            secret_key=secret,
            max_upload_bytes=int(os.environ.get("MAX_UPLOAD_BYTES", 2 * 1024 * 1024)),
            max_content_bytes=int(os.environ.get("MAX_CONTENT_BYTES", 1 * 1024 * 1024)),
            seed_demo_users=_bool(os.environ.get("SEED_DEMO_USERS"), True),
            seed_sample_content=_bool(os.environ.get("SEED_SAMPLE_CONTENT"), True),
            cookie_secure=_bool(os.environ.get("COOKIE_SECURE"), False),
            static_dir=os.environ.get("STATIC_DIR") or None,
        )
