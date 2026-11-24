"""Runtime configuration from environment variables (and an optional aria-x/.env)."""
import os
from pathlib import Path

from cryptography.fernet import Fernet

from . import ROOT

DATA_DIR = Path(os.environ.get("ARIAX_DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_env_file(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


_load_env_file(ROOT / ".env")

ENV = os.environ.get("ARIAX_ENV", "development")
PRODUCTION = ENV == "production"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'ariax.db').as_posix()}")
BASE_URL = os.environ.get("ARIAX_BASE_URL", "http://localhost:8700").rstrip("/")
COOKIE_SECURE = os.environ.get("ARIAX_COOKIE_SECURE", "1" if PRODUCTION else "0") == "1"
SESSION_DAYS = int(os.environ.get("ARIAX_SESSION_DAYS", "14"))
ENABLE_MOCK_LLM = os.environ.get("ARIAX_ENABLE_MOCK_LLM", "0") == "1"
UPLOAD_LIMIT_MB = int(os.environ.get("ARIAX_UPLOAD_LIMIT_MB", "25"))
WEBHOOK_TIMEOUT = float(os.environ.get("ARIAX_WEBHOOK_TIMEOUT", "10"))


def _master_key() -> bytes:
    """Fernet key that encrypts every secret at rest. Required in production."""
    k = os.environ.get("ARIAX_MASTER_KEY")
    if k:
        return k.encode()
    if PRODUCTION:
        raise RuntimeError("ARIAX_MASTER_KEY must be set in production (generate one with: "
                           "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")")
    p = DATA_DIR / ".master_key"
    if not p.exists():
        p.write_bytes(Fernet.generate_key())
    return p.read_bytes().strip()


MASTER_KEY = _master_key()
