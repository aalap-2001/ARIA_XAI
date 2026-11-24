"""Request authentication → Access. Session cookie (+CSRF on writes) for the console; API keys for /v1."""
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import ApiKey, Membership, Role
from .models import Session as Sess
from .rbac import Access
from .security import sha

COOKIE = "ariax_session"
SAFE = {"GET", "HEAD", "OPTIONS"}


def _utc(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def session_access(request: Request, db: Session) -> tuple[Access, Membership, Sess] | None:
    tok = request.cookies.get(COOKIE)
    if not tok:
        return None
    s = db.get(Sess, sha(tok))
    if not s or _utc(s.expires_at) < datetime.now(timezone.utc):
        return None
    m = db.execute(select(Membership).where(Membership.org_id == s.org_id, Membership.user_id == s.user_id)).scalar()
    if not m or m.status != "active":
        return None
    a = Access(org_id=s.org_id, actor_id=m.user_id, actor_label=m.user.email, role_id=m.role.id, role_name=m.role.name,
               permissions=m.role.permissions, scopes=m.role.scopes, via="session")
    return a, m, s


def current(request: Request, db: Session = Depends(get_db)) -> Access:
    got = session_access(request, db)
    if not got:
        raise HTTPException(401, "Not signed in")
    a, _, s = got
    if request.method not in SAFE and request.headers.get("x-csrf-token") != s.csrf:
        raise HTTPException(403, "Missing or invalid CSRF token")
    return a


def require(*perms: str):
    def dep(a: Access = Depends(current)) -> Access:
        missing = [p for p in perms if not a.can(p)]
        if missing:
            raise HTTPException(403, f"Your role ({a.role_name}) does not allow: {', '.join(missing)}")
        return a
    return dep


def api_key_access(db: Session, raw: str, kind: str, origin: str | None = None) -> Access:
    k = db.execute(select(ApiKey).where(ApiKey.key_hash == sha(raw or ""))).scalar()
    if not k or k.revoked or k.kind != kind:
        raise HTTPException(401, "Invalid API key")
    if kind == "publishable":
        allowed = k.allowed_origins or []
        if "*" not in allowed and (origin or "") not in allowed:
            raise HTTPException(403, f"Origin {origin or '(none)'} is not allowed for this widget key")
    role = db.get(Role, k.role_id)
    k.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return Access(org_id=k.org_id, actor_id=k.id, actor_label=f"api-key:{k.name}", role_id=role.id, role_name=role.name,
                  permissions=role.permissions, scopes=role.scopes, via="api_key" if kind == "secret" else "widget")
