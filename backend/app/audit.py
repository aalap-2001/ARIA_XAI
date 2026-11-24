"""Per-organisation, hash-chained audit log. Editing history breaks the chain and verify() says where."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ariax.core.ids import canonical, sha256

from .models import AuditEntry

GENESIS = "0" * 64


def record(db: Session, org_id: str, actor: str, kind: str, target: str = "", detail: dict | None = None, commit=True):
    prev = db.execute(select(AuditEntry.hash).where(AuditEntry.org_id == org_id).order_by(AuditEntry.seq.desc()).limit(1)).scalar()
    prev = prev or GENESIS
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body = {"org_id": org_id, "at": at, "actor": actor, "kind": kind, "target": target, "detail": detail or {}}
    entry = AuditEntry(org_id=org_id, at=at, actor=actor, kind=kind, target=target, detail=detail or {},
                       prev_hash=prev, hash=sha256(prev + canonical(body)))
    db.add(entry)
    if commit:
        db.commit()
    else:
        db.flush()
    return entry


def verify(db: Session, org_id: str) -> dict:
    prev, n = GENESIS, 0
    for e in db.execute(select(AuditEntry).where(AuditEntry.org_id == org_id).order_by(AuditEntry.seq)).scalars():
        body = {"org_id": e.org_id, "at": e.at, "actor": e.actor, "kind": e.kind, "target": e.target, "detail": e.detail}
        if e.prev_hash != prev or sha256(prev + canonical(body)) != e.hash:
            return {"ok": False, "entries": n, "broken_at": e.seq}
        prev, n = e.hash, n + 1
    return {"ok": True, "entries": n, "head": prev}
