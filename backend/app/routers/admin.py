"""Organisation, users, invitations and roles."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..config import BASE_URL
from ..db import get_db
from ..deps import require
from ..models import Blueprint, DataConnection, Invite, Membership, Organisation, Role
from ..rbac import RESOURCES, Access, check_permissions, normalise_scopes
from ..security import new_token, sha

router = APIRouter(prefix="/api", tags=["admin"])


# ------------------------------------------------------------------ organisation
@router.get("/org")
def get_org(a: Access = Depends(require("org:view")), db: Session = Depends(get_db)):
    o = db.get(Organisation, a.org_id)
    return {"id": o.id, "name": o.name, "settings": o.settings, "created_at": o.created_at}


@router.post("/org/kill-switch")
def set_kill_switch(body: dict, a: Access = Depends(require("org:edit")), db: Session = Depends(get_db)):
    """Halt every MEDIUM and HIGH risk action immediately (Sentinel kill switch), or release it."""
    o = db.get(Organisation, a.org_id)
    on = bool(body.get("active"))
    ks = {"active": on, "by": a.actor_label, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
          "reason": str(body.get("reason") or "")[:300]}
    o.settings = {**(o.settings or {}), "kill_switch": ks}
    audit.record(db, a.org_id, a.actor_label, "kill_switch.activated" if on else "kill_switch.released", o.id, {"reason": ks["reason"]}, commit=False)
    db.commit()
    return ks


@router.patch("/org")
def patch_org(body: dict, a: Access = Depends(require("org:edit")), db: Session = Depends(get_db)):
    o = db.get(Organisation, a.org_id)
    if "name" in body and str(body["name"]).strip():
        o.name = str(body["name"]).strip()[:200]
    if isinstance(body.get("settings"), dict):
        allowed = {"redact_contact_data", "max_agent_steps"}
        o.settings = {**o.settings, **{k: v for k, v in body["settings"].items() if k in allowed}}
    audit.record(db, a.org_id, a.actor_label, "org.updated", o.id, {"name": o.name, "settings": o.settings})
    return get_org(a, db)


# ------------------------------------------------------------------ users & invites
class InviteIn(BaseModel):
    email: EmailStr
    role_id: str


@router.get("/users")
def list_users(a: Access = Depends(require("users:view")), db: Session = Depends(get_db)):
    ms = db.execute(select(Membership).where(Membership.org_id == a.org_id).order_by(Membership.created_at)).scalars().all()
    invs = db.execute(select(Invite).where(Invite.org_id == a.org_id, Invite.accepted_at.is_(None))).scalars().all()
    nowt = datetime.now(timezone.utc)
    return {
        "members": [{"id": m.id, "user_id": m.user.id, "name": m.user.name, "email": m.user.email, "role_id": m.role_id,
                     "role": m.role.name, "status": m.status, "last_login_at": m.user.last_login_at, "joined_at": m.created_at,
                     "you": m.user_id == a.actor_id} for m in ms],
        "invites": [{"id": i.id, "email": i.email, "role_id": i.role_id, "role": db.get(Role, i.role_id).name, "expires_at": i.expires_at,
                     "expired": (i.expires_at if i.expires_at.tzinfo else i.expires_at.replace(tzinfo=timezone.utc)) < nowt} for i in invs],
    }


@router.post("/users/invite")
def invite(body: InviteIn, a: Access = Depends(require("users:create")), db: Session = Depends(get_db)):
    role = db.get(Role, body.role_id)
    if not role or role.org_id != a.org_id:
        raise HTTPException(404, "Role not found")
    if role.name == "Owner" and "*" not in a.permissions:
        raise HTTPException(403, "Only an Owner can invite another Owner")
    email = body.email.lower()
    existing = db.execute(select(Membership).join(Membership.user).where(Membership.org_id == a.org_id)).scalars().all()
    if any(m.user.email == email and m.status == "active" for m in existing):
        raise HTTPException(409, "This person is already a member")
    tok = new_token()
    db.add(Invite(org_id=a.org_id, email=email, role_id=role.id, token_hash=sha(tok), created_by=a.actor_id,
                  expires_at=datetime.now(timezone.utc) + timedelta(days=7)))
    audit.record(db, a.org_id, a.actor_label, "user.invited", email, {"role": role.name}, commit=False)
    db.commit()
    return {"email": email, "role": role.name, "invite_url": f"{BASE_URL}/invite/{tok}", "expires_in_days": 7}


@router.delete("/invites/{invite_id}")
def revoke_invite(invite_id: str, a: Access = Depends(require("users:delete")), db: Session = Depends(get_db)):
    inv = db.get(Invite, invite_id)
    if not inv or inv.org_id != a.org_id:
        raise HTTPException(404, "Invitation not found")
    db.delete(inv)
    audit.record(db, a.org_id, a.actor_label, "user.invite_revoked", inv.email, commit=False)
    db.commit()
    return {"ok": True}


def _owners(db, org_id):
    return db.execute(select(func.count()).select_from(Membership).join(Role, Role.id == Membership.role_id)
                      .where(Membership.org_id == org_id, Role.name == "Owner", Role.builtin.is_(True), Membership.status == "active")).scalar()


@router.patch("/users/{membership_id}")
def update_member(membership_id: str, body: dict, a: Access = Depends(require("users:edit")), db: Session = Depends(get_db)):
    m = db.get(Membership, membership_id)
    if not m or m.org_id != a.org_id:
        raise HTTPException(404, "Member not found")
    if m.user_id == a.actor_id:
        raise HTTPException(400, "You cannot change your own role or status")
    was_owner = m.role.name == "Owner" and m.role.builtin
    if "role_id" in body:
        role = db.get(Role, body["role_id"])
        if not role or role.org_id != a.org_id:
            raise HTTPException(404, "Role not found")
        if (role.name == "Owner" or was_owner) and "*" not in a.permissions:
            raise HTTPException(403, "Only an Owner can grant or remove the Owner role")
        if was_owner and role.id != m.role_id and _owners(db, a.org_id) <= 1:
            raise HTTPException(400, "An organisation must keep at least one Owner")
        m.role_id = role.id
    if "status" in body:
        if body["status"] not in ("active", "deactivated"):
            raise HTTPException(400, "status must be active or deactivated")
        if was_owner and body["status"] == "deactivated" and _owners(db, a.org_id) <= 1:
            raise HTTPException(400, "An organisation must keep at least one Owner")
        m.status = body["status"]
    audit.record(db, a.org_id, a.actor_label, "user.updated", m.user.email, {"role_id": m.role_id, "status": m.status}, commit=False)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ roles
def role_out(r: Role, counts: dict) -> dict:
    return {"id": r.id, "name": r.name, "description": r.description, "builtin": r.builtin, "permissions": r.permissions,
            "scopes": r.scopes, "members": counts.get(r.id, 0), "locked": r.builtin and r.name == "Owner"}


@router.get("/roles")
def list_roles(a: Access = Depends(require("users:view")), db: Session = Depends(get_db)):
    rows = db.execute(select(Role).where(Role.org_id == a.org_id).order_by(Role.builtin.desc(), Role.name)).scalars().all()
    counts = dict(db.execute(select(Membership.role_id, func.count()).where(Membership.org_id == a.org_id, Membership.status == "active")
                             .group_by(Membership.role_id)).all())
    return [role_out(r, counts) for r in rows]


@router.get("/roles/catalog")
def roles_catalog(a: Access = Depends(require("roles:view")), db: Session = Depends(get_db)):
    """Everything a role can be granted: permissions, plus the scope options that exist in this org right now."""
    bp = db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id, Blueprint.status == "published")).scalar()
    content = bp.content if bp else {}
    conns = db.execute(select(DataConnection).where(DataConnection.org_id == a.org_id)).scalars().all()
    return {
        "resources": [{"id": k, "label": v[0], "actions": v[1]} for k, v in RESOURCES.items() if k != "llm"],  # AI models are set on the server
        # The four built-in agents first, then this organisation's specialist sub-agents.
        "team": [{"id": "orchestrator", "name": "Aria Orchestrator", "purpose": "Plans, coordinates and ensures everything follows the rules."},
                 {"id": "analyst", "name": "Aria Analyst", "purpose": "Reads company data and answers questions."},
                 {"id": "executor", "name": "Aria Executor", "purpose": "Makes approved changes to the product."},
                 {"id": "watch", "name": "Aria Watch", "purpose": "Monitors activity and suggests improvements."}],
        "agents": [{"id": x["id"], "name": x["name"]} for x in content.get("agents", [])],
        "actions": [{"name": x["name"], "risk": x.get("risk")} for x in content.get("actions", [])],
        "data": [{"id": c.id, "name": c.name, "tables": [t["name"] for t in (c.schema_snapshot or {}).get("tables", [])]} for c in conns],
    }


class RoleIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = ""
    permissions: list[str] = []
    scopes: dict = {}


@router.post("/roles")
def create_role(body: RoleIn, a: Access = Depends(require("roles:create")), db: Session = Depends(get_db)):
    if db.execute(select(Role).where(Role.org_id == a.org_id, Role.name == body.name.strip())).scalar():
        raise HTTPException(409, "A role with this name already exists")
    try:
        perms = check_permissions(body.permissions)
    except ValueError as ex:
        raise HTTPException(400, str(ex)) from ex
    if "*" in perms and "*" not in a.permissions:
        raise HTTPException(403, "Only an Owner can create a role with full access")
    r = Role(org_id=a.org_id, name=body.name.strip(), description=body.description[:500], permissions=perms, scopes=normalise_scopes(body.scopes))
    db.add(r)
    audit.record(db, a.org_id, a.actor_label, "role.created", r.name, {"permissions": perms, "scopes": r.scopes}, commit=False)
    db.commit()
    return role_out(r, {})


@router.patch("/roles/{role_id}")
def update_role(role_id: str, body: RoleIn, a: Access = Depends(require("roles:edit")), db: Session = Depends(get_db)):
    r = db.get(Role, role_id)
    if not r or r.org_id != a.org_id:
        raise HTTPException(404, "Role not found")
    if r.builtin and r.name == "Owner":
        raise HTTPException(400, "The Owner role always has full access and cannot be edited")
    try:
        perms = check_permissions(body.permissions)
    except ValueError as ex:
        raise HTTPException(400, str(ex)) from ex
    if "*" in perms and "*" not in a.permissions:
        raise HTTPException(403, "Only an Owner can grant full access")
    if not r.builtin:
        r.name = body.name.strip()
    r.description, r.permissions, r.scopes = body.description[:500], perms, normalise_scopes(body.scopes)
    audit.record(db, a.org_id, a.actor_label, "role.updated", r.name, {"permissions": perms, "scopes": r.scopes}, commit=False)
    db.commit()
    return role_out(r, {})


@router.delete("/roles/{role_id}")
def delete_role(role_id: str, a: Access = Depends(require("roles:delete")), db: Session = Depends(get_db)):
    r = db.get(Role, role_id)
    if not r or r.org_id != a.org_id:
        raise HTTPException(404, "Role not found")
    if r.builtin:
        raise HTTPException(400, "Built-in roles cannot be deleted")
    if db.execute(select(func.count()).select_from(Membership).where(Membership.role_id == r.id)).scalar():
        raise HTTPException(400, "Move the members of this role to another role first")
    db.delete(r)
    audit.record(db, a.org_id, a.actor_label, "role.deleted", r.name, commit=False)
    db.commit()
    return {"ok": True}
