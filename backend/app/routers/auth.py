from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..config import COOKIE_SECURE, SESSION_DAYS
from ..db import get_db
from ..deps import COOKIE, session_access
from ..models import Invite, Membership, Organisation, Role, User
from ..models import Session as Sess
from ..rbac import BUILTIN_ROLES
from ..security import encrypt_json, hash_password, login_limiter, new_token, password_problem, sha, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


class SignUp(BaseModel):
    org_name: str = Field(min_length=2, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str


class Login(BaseModel):
    email: str = Field(min_length=1, max_length=320)  # an email address or a username
    password: str
    org_id: str | None = None


class Accept(BaseModel):
    name: str = Field(default="", max_length=200)
    password: str


def create_org(db: Session, name: str) -> tuple[Organisation, dict[str, Role]]:
    org = Organisation(name=name.strip(), settings={"redact_contact_data": True},
                       webhook_secret_enc=encrypt_json({"secret": new_token("whsec_")}))
    db.add(org)
    db.flush()
    roles = {}
    for r in BUILTIN_ROLES:
        role = Role(org_id=org.id, name=r["name"], description=r["description"], builtin=True, permissions=r["permissions"], scopes=r["scopes"])
        db.add(role)
        roles[r["name"]] = role
    db.flush()
    return org, roles


def start_session(db: Session, response: Response, request: Request, user: User, org_id: str) -> str:
    tok = new_token()
    csrf = new_token(n=24)
    db.add(Sess(id=sha(tok), user_id=user.id, org_id=org_id, csrf=csrf, ip=(request.client.host if request.client else ""),
                expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)))
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    response.set_cookie(COOKIE, tok, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=SESSION_DAYS * 86400, path="/")
    return csrf


def me_payload(db: Session, a, m: Membership, s: Sess) -> dict:
    org = db.get(Organisation, a.org_id)
    orgs = db.execute(select(Membership).where(Membership.user_id == m.user_id, Membership.status == "active")).scalars().all()
    return {"user": {"id": m.user.id, "name": m.user.name, "email": m.user.email},
            "org": {"id": org.id, "name": org.name, "kill_switch": ((org.settings or {}).get("kill_switch") or {}) if ((org.settings or {}).get("kill_switch") or {}).get("active") else None},
            "csrf": s.csrf, **a.public(),
            "orgs": [{"id": x.org_id, "name": db.get(Organisation, x.org_id).name, "role": x.role.name, "industry": _industry(db, x.org_id),
                      "created": (lambda o: o.created_at.isoformat() if o.created_at else "")(db.get(Organisation, x.org_id))} for x in orgs]}


def _industry(db, org_id: str) -> str:
    """What the business is, as Aria XAI understood it (shown in the business switcher)."""
    from ..models import Blueprint
    bp = db.execute(select(Blueprint).where(Blueprint.org_id == org_id, Blueprint.status == "published")).scalar()
    return ((bp.content or {}).get("industry") or "") if bp else ""


@router.post("/auth/signup")
def signup(body: SignUp, request: Request, response: Response, db: Session = Depends(get_db)):
    if p := password_problem(body.password):
        raise HTTPException(400, p)
    email = body.email.lower()
    if db.execute(select(User).where(User.email == email)).scalar():
        raise HTTPException(409, "An account with this email already exists, sign in instead")
    org, roles = create_org(db, body.org_name)
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    db.add(Membership(org_id=org.id, user_id=user.id, role_id=roles["Owner"].id))
    audit.record(db, org.id, email, "org.created", org.id, {"name": org.name}, commit=False)
    db.commit()
    start_session(db, response, request, user, org.id)
    return {"ok": True}


@router.post("/auth/login")
def login(body: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    ident = body.email.strip().lower()
    key = f"{request.client.host if request.client else ''}:{ident}"
    if not login_limiter.hit(key):
        raise HTTPException(429, "Too many sign-in attempts. Try again in 15 minutes.")
    by = User.email if "@" in ident else User.username
    user = db.execute(select(User).where(by == ident)).scalar()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email, username or password is incorrect")
    email = user.email
    ms = db.execute(select(Membership).where(Membership.user_id == user.id, Membership.status == "active")).scalars().all()
    if not ms:
        raise HTTPException(403, "Your access has been deactivated. Contact your organisation admin.")
    m = next((x for x in ms if x.org_id == body.org_id), ms[0])
    login_limiter.reset(key)
    start_session(db, response, request, user, m.org_id)
    audit.record(db, m.org_id, email, "auth.login", user.id)
    return {"ok": True}


@router.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    tok = request.cookies.get(COOKIE)
    if tok and (s := db.get(Sess, sha(tok))):
        db.delete(s)
        db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request, db: Session = Depends(get_db)):
    got = session_access(request, db)
    if not got:
        raise HTTPException(401, "Not signed in")
    return me_payload(db, *got)


@router.post("/auth/switch")
def switch(body: dict, request: Request, response: Response, db: Session = Depends(get_db)):
    got = session_access(request, db)
    if not got:
        raise HTTPException(401, "Not signed in")
    a, m, s = got
    if request.headers.get("x-csrf-token") != s.csrf:
        raise HTTPException(403, "Missing or invalid CSRF token")
    target = db.execute(select(Membership).where(Membership.user_id == m.user_id, Membership.org_id == body.get("org_id"),
                                                 Membership.status == "active")).scalar()
    if not target:
        raise HTTPException(404, "You are not a member of that organisation")
    db.delete(s)
    db.commit()
    start_session(db, response, request, m.user, target.org_id)
    return {"ok": True}


def _invite(db: Session, token: str) -> Invite:
    inv = db.execute(select(Invite).where(Invite.token_hash == sha(token))).scalar()
    exp = inv and (inv.expires_at if inv.expires_at.tzinfo else inv.expires_at.replace(tzinfo=timezone.utc))
    if not inv or inv.accepted_at or exp < datetime.now(timezone.utc):
        raise HTTPException(404, "This invitation is invalid or has expired")
    return inv


@router.get("/invites/{token}")
def invite_info(token: str, db: Session = Depends(get_db)):
    inv = _invite(db, token)
    existing = db.execute(select(User).where(User.email == inv.email)).scalar()
    return {"email": inv.email, "org": db.get(Organisation, inv.org_id).name, "role": db.get(Role, inv.role_id).name,
            "existing_account": bool(existing)}


@router.post("/invites/{token}/accept")
def invite_accept(token: str, body: Accept, request: Request, response: Response, db: Session = Depends(get_db)):
    inv = _invite(db, token)
    user = db.execute(select(User).where(User.email == inv.email)).scalar()
    if user:
        if not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "Enter the password of your existing Aria XAI account to join")
    else:
        if p := password_problem(body.password):
            raise HTTPException(400, p)
        user = User(email=inv.email, name=(body.name or inv.email.split("@")[0]).strip(), password_hash=hash_password(body.password))
        db.add(user)
        db.flush()
    m = db.execute(select(Membership).where(Membership.org_id == inv.org_id, Membership.user_id == user.id)).scalar()
    if m:
        m.role_id, m.status = inv.role_id, "active"
    else:
        db.add(Membership(org_id=inv.org_id, user_id=user.id, role_id=inv.role_id))
    inv.accepted_at = datetime.now(timezone.utc)
    audit.record(db, inv.org_id, inv.email, "user.joined", user.id, {"role_id": inv.role_id}, commit=False)
    db.commit()
    start_session(db, response, request, user, inv.org_id)
    return {"ok": True}
