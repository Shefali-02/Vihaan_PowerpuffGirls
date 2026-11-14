"""Password hashing (PBKDF2, stdlib) and JWT issue/verify."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from core.config import get_settings
from core.errors import Unauthenticated

ROLES = ("ACCOUNTANT", "CA", "INVESTOR")
_ITER = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITER)
    return f"pbkdf2${_ITER}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt_b64, dk_b64 = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iters))
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except Exception:
        return False


def issue_token(*, user_id: str, workspace_id: str, role: str) -> tuple[str, int]:
    s = get_settings()
    ttl = s.JWT_TTL_MINUTES * 60
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "ws": workspace_id, "role": role, "iat": now, "exp": now + timedelta(seconds=ttl)}
    return jwt.encode(payload, s.JWT_SECRET, algorithm="HS256"), ttl


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, get_settings().JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise Unauthenticated("Invalid or expired token") from e
