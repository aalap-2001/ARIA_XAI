"""Secrets at rest, password hashing, tokens, rate limiting."""
import base64
import hashlib
import hmac
import json
import secrets
import threading
import time

from cryptography.fernet import Fernet, InvalidToken

from .config import MASTER_KEY

_fernet = Fernet(MASTER_KEY)


# ---------------------------------------------------------------- encryption at rest
def encrypt_json(obj: dict) -> str:
    return _fernet.encrypt(json.dumps(obj).encode()).decode()


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet.encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _fernet.decrypt(token)
    except InvalidToken as ex:
        raise RuntimeError("Stored file cannot be decrypted, was ARIAX_MASTER_KEY changed?") from ex


def decrypt_json(token: str | None) -> dict:
    if not token:
        return {}
    try:
        return json.loads(_fernet.decrypt(token.encode()))
    except InvalidToken as ex:
        raise RuntimeError("Stored secret cannot be decrypted, was ARIAX_MASTER_KEY changed?") from ex


def hint(value: str | None) -> str:
    v = (value or "").strip()
    return ("••••" + v[-4:]) if len(v) >= 8 else ("••••" if v else "")


# ---------------------------------------------------------------- passwords (scrypt)
_N, _R, _P = 2 ** 14, 8, 1


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:  # noqa: BLE001
        return False


def password_problem(pw: str) -> str | None:
    if len(pw or "") < 10:
        return "Password must be at least 10 characters"
    if pw.lower() == pw or pw.upper() == pw or not any(c.isdigit() for c in pw):
        return "Password must mix upper and lower case letters and include a digit"
    return None


# ---------------------------------------------------------------- tokens
def new_token(prefix: str = "", n: int = 32) -> str:
    return prefix + secrets.token_urlsafe(n)


def sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------- rate limiting
class RateLimiter:
    def __init__(self, limit: int, window_s: int):
        self.limit, self.window = limit, window_s
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        """Record an attempt. Returns False when the key is over its limit."""
        t = time.time()
        with self._lock:
            hits = [h for h in self._hits.get(key, []) if h > t - self.window]
            hits.append(t)
            self._hits[key] = hits
            return len(hits) <= self.limit

    def reset(self, key: str):
        with self._lock:
            self._hits.pop(key, None)


login_limiter = RateLimiter(limit=10, window_s=900)
