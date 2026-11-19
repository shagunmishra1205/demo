"""Small standard-library authentication helpers (no third-party auth dependency)."""
import base64
import hashlib
import hmac
import json
import secrets
import time

from .config import settings

_ITERATIONS = 310_000
_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = _b64decode(digest_text)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _b64decode(salt_text), int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + _TOKEN_TTL_SECONDS}
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(settings.auth_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64encode(signature)}"


def read_access_token(token: str) -> str | None:
    try:
        encoded, signature_text = token.split(".", 1)
        expected = hmac.new(
            settings.auth_secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(signature_text)):
            return None
        payload = json.loads(_b64decode(encoded))
        if not isinstance(payload.get("sub"), str) or int(payload.get("exp", 0)) <= int(time.time()):
            return None
        return payload["sub"]
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
