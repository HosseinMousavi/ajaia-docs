"""Password hashing (stdlib scrypt) and signed session tokens."""

from __future__ import annotations

import hashlib
import hmac
import os

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    except ValueError:
        return False
    return hmac.compare_digest(candidate.hex(), digest_hex)


class SessionSigner:
    def __init__(self, secret_key: str, max_age_seconds: int) -> None:
        self._s = URLSafeTimedSerializer(secret_key, salt="ajaia-session")
        self._max_age = max_age_seconds

    def issue(self, user_id: int) -> str:
        return self._s.dumps({"uid": user_id})

    def read(self, token: str) -> int | None:
        try:
            data = self._s.loads(token, max_age=self._max_age)
        except (BadSignature, SignatureExpired):
            return None
        uid = data.get("uid") if isinstance(data, dict) else None
        return uid if isinstance(uid, int) else None
