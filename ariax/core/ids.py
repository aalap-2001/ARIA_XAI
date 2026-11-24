"""§03.2, trace_id spans the request (minted at the edge); decision_id is minted by Sentinel."""
import hashlib
import json
import uuid
from datetime import datetime, timezone


def _hex(n: int) -> str:
    return uuid.uuid4().hex[:n]


def new_trace_id() -> str:
    return "tr_" + _hex(20)


def new_decision_id() -> str:
    return "dc_" + _hex(20)


def new_id(prefix: str) -> str:
    return f"{prefix}_" + _hex(16)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical(value) -> str:
    """Stable JSON so hashes and signatures are reproducible."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
