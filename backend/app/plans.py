"""Plans: the only way anything gets written. Aria Executor proposes; the responsible human approves; then each
step goes through the neuro-symbolic decision path with that human as the accountable party."""
from datetime import datetime, timezone

from sqlalchemy import select

from . import audit, decisions
from .models import Blueprint, Plan
from .rbac import Access


def published(db, org_id) -> Blueprint | None:
    return db.execute(select(Blueprint).where(Blueprint.org_id == org_id, Blueprint.status == "published")).scalar()


def preview_steps(bp: Blueprint, steps: list, approver: Access | None) -> list:
    """Annotate each proposed step with the rule verdict and the approver's authority, before anyone approves."""
    out = []
    for s in steps:
        a = next((x for x in bp.content.get("actions", []) if x["name"] == s.get("action")), None)
        if not a:
            out.append({**s, "error": f"Unknown action '{s.get('action')}'"})
            continue
        ex = decisions.evaluate(bp.content, a["name"], s.get("facts") or {}, bp.version, s.get("evidence"))
        amount = None
        if a.get("amount_fact") and (s.get("facts") or {}).get(a["amount_fact"]) not in (None, ""):
            try:
                amount = float(s["facts"][a["amount_fact"]])
            except (TypeError, ValueError):
                amount = None
        out.append({**s, "risk": a["risk"], "owner_role": a.get("owner_role"), "amount": amount,
                    "executor": (a.get("executor") or {}).get("type", "webhook"),
                    "verdict": ex["verdict"], "rules": [{"id": h["id"], "status": h["status"], "message": h.get("message")} for h in ex["hard"]],
                    "authority": decisions.authority(approver, a, amount) if approver else None})
    return out


def create(db, org_id: str, title: str, summary: str, steps: list, *, source: str, conversation_id: str | None = None,
           approver: Access | None = None, owner_role: str | None = None, suggestion_id: str | None = None, actor: str = "Aria Executor") -> Plan:
    bp = published(db, org_id)
    p = Plan(org_id=org_id, conversation_id=conversation_id, source=source, suggestion_id=suggestion_id, title=title[:300], summary=summary or "",
             steps=preview_steps(bp, steps, approver) if bp else steps, approver_user_id=approver.actor_id if approver and approver.via == "session" else None,
             owner_role=owner_role)
    db.add(p)
    db.flush()
    audit.record(db, org_id, actor, "plan.proposed", p.id, {"title": p.title, "steps": [s.get("action") for s in steps],
                                                           "approver": approver.actor_label if approver else owner_role}, commit=False)
    db.commit()
    return p


def can_decide(access: Access, p: Plan) -> bool:
    if p.approver_user_id:
        return access.actor_id == p.approver_user_id
    return decisions.is_owner(access, p.owner_role)


def decide(db, access: Access, p: Plan, approve: bool, note: str = "") -> Plan:
    if p.status != "awaiting_approval":
        raise ValueError(f"This plan is already {p.status.replace('_', ' ')}")
    if not can_decide(access, p):
        raise PermissionError("Only the person this plan was proposed to" + (f" (or the {p.owner_role} role)" if p.owner_role else "") + " can decide it")
    if approve and not access.can_use_agent("executor"):
        raise PermissionError(f"Your role ({access.role_name}) does not include Aria Executor, so it cannot run changes for you")
    p.decided_at = datetime.now(timezone.utc)
    if not approve:
        p.status, p.accountable = "rejected", access.actor_label
        audit.record(db, p.org_id, access.actor_label, "plan.rejected", p.id, {"note": note}, commit=False)
        db.commit()
        return p
    p.status, p.accountable = "approved", access.actor_label
    audit.record(db, p.org_id, access.actor_label, "plan.approved", p.id, {"note": note, "steps": len(p.steps)}, commit=False)
    db.commit()
    bp = published(db, p.org_id)
    results = []
    for s in p.steps:
        if not bp or s.get("error"):
            results.append({"action": s.get("action"), "status": "BLOCKED", "reasons": [s.get("error") or "No published blueprint"]})
            continue
        d = decisions.propose(db, access, bp, "executor", s["action"], s.get("facts") or {}, s.get("payload") or {},
                              s.get("summary") or p.summary, p.conversation_id, accountable=access, plan_id=p.id,
                              evidence=s.get("evidence"))
        results.append({"decision_id": d.id, "action": d.action, "verdict": d.verdict, "effect": d.effect, "status": d.status,
                        "reasons": d.reasons, "execution": d.execution})
    st = {r["status"] for r in results}
    p.results = results
    p.status = "executed" if st <= {"EXECUTED"} else "escalated" if "PENDING_REVIEW" in st and not st & {"FAILED", "BLOCKED"} else \
        "blocked" if st <= {"BLOCKED"} else "partial"
    db.commit()
    return p


def out(p: Plan) -> dict:
    return {"id": p.id, "title": p.title, "summary": p.summary, "steps": p.steps, "status": p.status, "source": p.source,
            "owner_role": p.owner_role, "approver_user_id": p.approver_user_id, "accountable": p.accountable, "results": p.results,
            "suggestion_id": p.suggestion_id, "conversation_id": p.conversation_id, "created_at": p.created_at, "decided_at": p.decided_at}
