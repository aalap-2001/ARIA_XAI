"""Approvals, decisions, audit, usage, API keys and webhook settings."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .. import audit, decisions, plans
from ..db import get_db
from ..deps import require
from ..models import ApiKey, AuditEntry, Decision, Event, LLMConnector, Organisation, Plan, Role, Suggestion, UsageEvent
from ..rbac import Access
from ..security import decrypt_json, encrypt_json, new_token, sha

router = APIRouter(prefix="/api", tags=["govern"])


def dec_out(d: Decision, full=False) -> dict:
    o = {"id": d.id, "agent": d.agent, "action": d.action, "risk": d.risk, "verdict": d.verdict, "effect": d.effect, "status": d.status,
         "amount": d.amount, "summary": d.summary, "reasons": d.reasons, "requested_by": d.requested_by, "reviewer": d.reviewer,
         "review_note": d.review_note, "created_at": d.created_at, "updated_at": d.updated_at, "blueprint_version": d.blueprint_version,
         "conversation_id": d.conversation_id, "facts": d.facts, "accountable": d.accountable, "owner_role": d.owner_role, "plan_id": d.plan_id}
    if full:
        o.update({"payload": d.payload, "payload_hash": d.payload_hash, "explanation": d.explanation, "execution": d.execution})
    return o


@router.get("/decisions")
def list_decisions(status: str | None = None, mine: bool = False, a: Access = Depends(require("approvals:view")), db: Session = Depends(get_db)):
    q = select(Decision).where(Decision.org_id == a.org_id)
    if status:
        q = q.where(Decision.status == status)
    if mine and "*" not in a.permissions:  # escalations waiting for MY role
        q = q.where(Decision.owner_role == a.role_name)
    if not a.can("audit:view") and not a.can("approvals:approve"):
        q = q.where(Decision.requested_by == a.actor_label)  # operators see their own requests
    return [dec_out(d) for d in db.execute(q.order_by(Decision.created_at.desc()).limit(300)).scalars()]


@router.get("/decisions/{did}")
def get_decision(did: str, a: Access = Depends(require("approvals:view")), db: Session = Depends(get_db)):
    d = db.get(Decision, did)
    if not d or d.org_id != a.org_id:
        raise HTTPException(404, "Decision not found")
    trail = db.execute(select(AuditEntry).where(AuditEntry.org_id == a.org_id, AuditEntry.target == d.id).order_by(AuditEntry.seq)).scalars().all()
    return {**dec_out(d, True), "audit": [{"seq": e.seq, "at": e.at, "actor": e.actor, "kind": e.kind, "detail": e.detail, "hash": e.hash} for e in trail]}


class ReviewIn(BaseModel):
    approve: bool
    note: str = ""


@router.post("/decisions/{did}/review")
def review(did: str, body: ReviewIn, a: Access = Depends(require("approvals:approve")), db: Session = Depends(get_db)):
    d = db.get(Decision, did)
    if not d or d.org_id != a.org_id:
        raise HTTPException(404, "Decision not found")
    try:
        decisions.review(db, a, d, body.approve, body.note)
    except PermissionError as ex:
        raise HTTPException(403, str(ex)) from ex
    except ValueError as ex:
        raise HTTPException(409, str(ex)) from ex
    return dec_out(d, True)


# ------------------------------------------------------------------ plans (Aria Executor), approved by the responsible person
@router.get("/plans")
def list_plans(status: str | None = None, a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    q = select(Plan).where(Plan.org_id == a.org_id)
    if status:
        q = q.where(Plan.status == status)
    rows = db.execute(q.order_by(Plan.created_at.desc()).limit(200)).scalars().all()
    return [plans.out(p) | {"can_decide": plans.can_decide(a, p)} for p in rows
            if p.approver_user_id == a.actor_id or plans.can_decide(a, p) or a.can("audit:view")]


@router.get("/plans/{pid}")
def get_plan(pid: str, a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    p = db.get(Plan, pid)
    if not p or p.org_id != a.org_id or not (p.approver_user_id == a.actor_id or plans.can_decide(a, p) or a.can("audit:view")):
        raise HTTPException(404, "Plan not found")
    return plans.out(p) | {"can_decide": plans.can_decide(a, p) and p.status == "awaiting_approval"}


@router.post("/plans/{pid}/decide")
def decide_plan(pid: str, body: ReviewIn, a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    p = db.get(Plan, pid)
    if not p or p.org_id != a.org_id:
        raise HTTPException(404, "Plan not found")
    try:
        plans.decide(db, a, p, body.approve, body.note)
    except PermissionError as ex:
        raise HTTPException(403, str(ex)) from ex
    except ValueError as ex:
        raise HTTPException(409, str(ex)) from ex
    return plans.out(p) | {"can_decide": False}


# ------------------------------------------------------------------ Aria Watch: events and suggestions
def _watch(a: Access):
    if not a.can_use_agent("watch"):
        raise HTTPException(403, f"Your role ({a.role_name}) does not include Aria Watch")


@router.get("/events")
def list_events(status: str | None = None, a: Access = Depends(require("approvals:view")), db: Session = Depends(get_db)):
    _watch(a)
    q = select(Event).where(Event.org_id == a.org_id)
    if status:
        q = q.where(Event.status == status)
    return [{"id": e.id, "type": e.type, "entity_id": e.entity_id, "actor": e.actor, "data": e.data, "occurred_at": e.occurred_at,
             "received_at": e.received_at, "status": e.status, "matched_rule": e.matched_rule, "note": e.note, "trace": e.trace,
             "suggestion_id": e.suggestion_id} for e in db.execute(q.order_by(Event.received_at.desc()).limit(300)).scalars()]


def sug_out(s: Suggestion, a: Access) -> dict:
    return {"id": s.id, "event_id": s.event_id, "title": s.title, "rationale": s.rationale, "benefit": s.benefit, "owner_role": s.owner_role,
            "steps": s.steps, "status": s.status, "decided_by": s.decided_by, "note": s.note, "plan_id": s.plan_id, "created_at": s.created_at,
            "decided_at": s.decided_at, "can_decide": s.status == "pending" and decisions.is_owner(a, s.owner_role) and a.can("approvals:approve")}


@router.get("/suggestions")
def list_suggestions(status: str | None = None, a: Access = Depends(require("approvals:view")), db: Session = Depends(get_db)):
    _watch(a)
    q = select(Suggestion).where(Suggestion.org_id == a.org_id)
    if status:
        q = q.where(Suggestion.status == status)
    return [sug_out(s, a) for s in db.execute(q.order_by(Suggestion.created_at.desc()).limit(200)).scalars()]


@router.post("/suggestions/{sid}/decide")
def decide_suggestion(sid: str, body: ReviewIn, a: Access = Depends(require("approvals:approve")), db: Session = Depends(get_db)):
    from .. import watch
    s = db.get(Suggestion, sid)
    if not s or s.org_id != a.org_id:
        raise HTTPException(404, "Suggestion not found")
    try:
        watch.decide(db, a, s, body.approve, body.note)
    except PermissionError as ex:
        raise HTTPException(403, str(ex)) from ex
    except ValueError as ex:
        raise HTTPException(409, str(ex)) from ex
    return sug_out(s, a) | {"plan": plans.out(db.get(Plan, s.plan_id)) if s.plan_id else None}


@router.get("/audit")
def audit_log(limit: int = 300, a: Access = Depends(require("audit:view")), db: Session = Depends(get_db)):
    rows = db.execute(select(AuditEntry).where(AuditEntry.org_id == a.org_id).order_by(AuditEntry.seq.desc()).limit(min(limit, 2000))).scalars()
    return [{"seq": e.seq, "at": e.at, "actor": e.actor, "kind": e.kind, "target": e.target, "detail": e.detail, "hash": e.hash} for e in rows]


@router.get("/audit/verify")
def audit_verify(a: Access = Depends(require("audit:view")), db: Session = Depends(get_db)):
    return audit.verify(db, a.org_id)


@router.get("/audit/watchdog")
def audit_watchdog(a: Access = Depends(require("audit:view")), db: Session = Depends(get_db)):
    """Reconcile every outbound send against an approved decision."""
    return decisions.watchdog(db, a.org_id)


@router.get("/usage")
def usage(days: int = 30, a: Access = Depends(require("usage:view")), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=min(days, 365))
    rows = db.execute(select(func.date(UsageEvent.at), UsageEvent.provider, UsageEvent.model, func.count(), func.sum(UsageEvent.input_tokens),
                             func.sum(UsageEvent.output_tokens), func.sum(case((UsageEvent.ok.is_(False), 1), else_=0)),
                             func.avg(UsageEvent.latency_ms))
                      .where(UsageEvent.org_id == a.org_id, UsageEvent.at >= since)
                      .group_by(func.date(UsageEvent.at), UsageEvent.provider, UsageEvent.model).order_by(func.date(UsageEvent.at).desc())).all()
    return [{"day": str(r[0]), "provider": r[1], "model": r[2], "calls": r[3], "input_tokens": r[4] or 0, "output_tokens": r[5] or 0,
             "errors": int(r[6] or 0), "avg_latency_ms": int(r[7] or 0)} for r in rows]


# ------------------------------------------------------------------ API keys & widget
class KeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str = "secret"
    role_id: str
    allowed_origins: list[str] = []


@router.get("/api-keys")
def list_keys(a: Access = Depends(require("api_keys:view")), db: Session = Depends(get_db)):
    rows = db.execute(select(ApiKey).where(ApiKey.org_id == a.org_id).order_by(ApiKey.created_at.desc())).scalars().all()
    return [{"id": k.id, "name": k.name, "kind": k.kind, "prefix": k.prefix, "role_id": k.role_id, "role": db.get(Role, k.role_id).name,
             "allowed_origins": k.allowed_origins, "revoked": k.revoked, "created_at": k.created_at, "last_used_at": k.last_used_at} for k in rows]


@router.post("/api-keys")
def create_key(body: KeyIn, a: Access = Depends(require("api_keys:create")), db: Session = Depends(get_db)):
    if body.kind not in ("secret", "publishable"):
        raise HTTPException(400, "kind must be secret or publishable")
    role = db.get(Role, body.role_id)
    if not role or role.org_id != a.org_id:
        raise HTTPException(404, "Role not found")
    if "*" in role.permissions:
        raise HTTPException(400, "API keys cannot act with full Owner access; choose or create a narrower role")
    if not role.permissions or "chat:use" not in role.permissions:
        raise HTTPException(400, "The role must include 'Agent team: use'")
    if body.kind == "publishable" and not body.allowed_origins:
        raise HTTPException(400, "A widget key needs at least one allowed origin (e.g. https://app.example.com)")
    raw = new_token("ax_sk_" if body.kind == "secret" else "ax_pk_", 30)
    k = ApiKey(org_id=a.org_id, name=body.name, kind=body.kind, prefix=raw[:12], key_hash=sha(raw), role_id=role.id,
               allowed_origins=[o.strip().rstrip("/") for o in body.allowed_origins if o.strip()], created_by=a.actor_id)
    db.add(k)
    audit.record(db, a.org_id, a.actor_label, "api_key.created", k.name, {"kind": k.kind, "role": role.name}, commit=False)
    db.commit()
    return {"id": k.id, "key": raw, "prefix": k.prefix, "note": "Copy this key now, it is shown only once."}


@router.delete("/api-keys/{kid}")
def revoke_key(kid: str, a: Access = Depends(require("api_keys:delete")), db: Session = Depends(get_db)):
    k = db.get(ApiKey, kid)
    if not k or k.org_id != a.org_id:
        raise HTTPException(404, "Key not found")
    k.revoked = True
    audit.record(db, a.org_id, a.actor_label, "api_key.revoked", k.name, commit=False)
    db.commit()
    return {"ok": True}


@router.get("/webhook-secret")
def webhook_secret(reveal: bool = False, a: Access = Depends(require("org:edit")), db: Session = Depends(get_db)):
    """The secret customers use to verify X-AriaX-Signature on action webhooks."""
    s = decrypt_json(db.get(Organisation, a.org_id).webhook_secret_enc).get("secret", "")
    if reveal:
        audit.record(db, a.org_id, a.actor_label, "webhook_secret.revealed", a.org_id)
    return {"secret": s if reveal else s[:10] + "••••••••"}


@router.post("/webhook-secret/rotate")
def rotate(a: Access = Depends(require("org:edit")), db: Session = Depends(get_db)):
    org = db.get(Organisation, a.org_id)
    org.webhook_secret_enc = encrypt_json({"secret": new_token("whsec_")})
    audit.record(db, a.org_id, a.actor_label, "webhook_secret.rotated", a.org_id, commit=False)
    db.commit()
    return {"ok": True}


@router.get("/dashboard")
def dashboard(a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    """The Command Centre for the signed-in person (see dashboard.py)."""
    from .. import dashboard as D
    return D.build(db, a)


@router.get("/home-stats")
def stats(a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    c = lambda *w: db.execute(select(func.count()).select_from(Decision).where(Decision.org_id == a.org_id, *w)).scalar()  # noqa: E731
    calls = db.execute(select(func.count()).select_from(UsageEvent).where(UsageEvent.org_id == a.org_id)).scalar()
    from ..llm.service import resolve
    default, shared_from = resolve(db, a.org_id)
    sg = db.execute(select(func.count()).select_from(Suggestion).where(Suggestion.org_id == a.org_id, Suggestion.status == "pending")).scalar()
    ev = db.execute(select(func.count()).select_from(Event).where(Event.org_id == a.org_id)).scalar()
    return {"suggestions": sg, "events": ev,
            "decisions": c(), "pending": c(Decision.status == "PENDING_REVIEW"), "executed": c(Decision.status == "EXECUTED"),
            "blocked": c(Decision.status == "BLOCKED"), "model_calls": calls,
            "default_model": {"name": default.name, "provider": default.provider, "model": default.model, "status": default.status,
                                "shared_from": shared_from.name if shared_from else None} if default else None}
