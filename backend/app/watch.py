"""Aria Watch, runs in the background on activity reported by the customer's product.

    product → POST /v1/events → symbolic triage with the blueprint's watch rules
        no rule matches                  → recorded and ignored (no model call; this is most events)
        a rule matches                   → Aria Watch investigates with read-only tools and sub-agents
            nothing would clearly help   → no_action (recorded, nobody is bothered)
            a change would help          → Suggestion to the area's owner role
                owner approves           → Aria Executor carries it out as a plan, the owner accountable
"""
import fnmatch
import queue
import threading
import traceback
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ariax.core import expr

from . import audit, plans, studio
from .agents import Team
from .db import SessionLocal
from .decisions import is_owner
from .llm.base import LLMError
from .models import Blueprint, Event, Organisation, Suggestion
from .rbac import FULL_SCOPES, Access

_q: queue.Queue = queue.Queue()
_started = False


def watch_access(org_id: str) -> Access:
    """Aria Watch reads with organisation-wide scope but holds no permission to act or approve."""
    return Access(org_id=org_id, actor_id="aria-watch", actor_label="Aria Watch", role_id="", role_name="Aria Watch",
                  permissions=["chat:use"], scopes=FULL_SCOPES, via="system")


def rule_matches(rule: dict, ev: Event) -> bool:
    if not fnmatch.fnmatchcase(ev.type, rule.get("event_type") or ""):
        return False
    if not rule.get("when"):
        return True
    ok, _ = expr.evaluate(rule["when"], {"type": ev.type, "entity_id": ev.entity_id, "actor": ev.actor, "data": ev.data})
    return ok is True


def ingest(db, org_id: str, body: dict) -> Event:
    ev = Event(org_id=org_id, type=str(body["type"])[:120], entity_id=str(body.get("entity_id") or "")[:200], actor=body.get("actor") or {},
               data=body.get("data") or {}, occurred_at=str(body.get("occurred_at") or "")[:40])
    db.add(ev)
    db.commit()
    _q.put(ev.id)
    return ev


def process(event_id: str):
    db = SessionLocal()
    try:
        ev = db.get(Event, event_id)
        if not ev or ev.status != "received":
            return
        bp = db.execute(select(Blueprint).where(Blueprint.org_id == ev.org_id, Blueprint.status == "published")).scalar()
        rule = next((r for r in ((bp.content if bp else {}).get("watch_rules") or []) if rule_matches(r, ev)), None)
        if not rule:
            ev.status, ev.note = "ignored", "No watch rule matched, not investigated"
            db.commit()
            return
        ev.matched_rule = rule["id"]
        motivation = studio.get(db.get(Organisation, ev.org_id), "motivation")
        if not motivation["watch_enabled"]:
            ev.status, ev.note = "ignored", "Aria Watch is paused in the Studio (Motivation Engine)"
            db.commit()
            return
        quiet = motivation["watch_cooldown_minutes"]
        since = datetime.now(timezone.utc) - timedelta(minutes=quiet)
        dup = db.execute(select(Event).where(Event.org_id == ev.org_id, Event.matched_rule == rule["id"], Event.entity_id == ev.entity_id,
                                             Event.id != ev.id, Event.status.in_(["investigating", "suggested"]), Event.received_at >= since)).scalar()
        if dup and ev.entity_id and quiet:
            ev.status, ev.note = "ignored", f"Already handled for {ev.entity_id} by {dup.id} in the last {quiet} minutes"
            db.commit()
            return
        ev.status = "investigating"
        db.commit()
        trace = []
        team = Team(db, watch_access(ev.org_id), None, trace.append, channel="watch")
        learned = lessons(db, ev.org_id, rule["id"])
        if learned:
            trace.append({"type": "warning", "agent": "watch", "depth": 0,
                          "text": f"Learning from {len(learned)} earlier owner decision(s) on this watch rule"})
        res = team.investigate({"id": ev.id, "type": ev.type, "entity_id": ev.entity_id, "actor": ev.actor, "data": ev.data,
                                "occurred_at": ev.occurred_at}, rule, learned)
        ev.trace = trace
        if res["outcome"] == "suggest":
            acts = {a["name"]: a for a in bp.content.get("actions", [])}
            owner = rule.get("owner_role") or (acts.get(res["steps"][0]["action"]) or {}).get("owner_role") or "Reviewer"
            s = Suggestion(org_id=ev.org_id, event_id=ev.id, title=res.get("title", "Suggested change")[:300], rationale=res.get("rationale", ""),
                           benefit=res.get("benefit", ""), owner_role=owner, steps=res.get("steps", []))
            db.add(s)
            db.flush()
            ev.status, ev.suggestion_id, ev.note = "suggested", s.id, f"Suggested to {owner}: {s.title}"
            audit.record(db, ev.org_id, "Aria Watch", "suggestion.created", s.id, {"event": ev.id, "rule": rule["id"], "owner_role": owner}, commit=False)
        else:
            ev.status, ev.note = "no_action", res.get("reason", "")[:2000]
        db.commit()
    except LLMError as ex:
        ev.status, ev.note = "failed", str(ex)
        db.commit()
    except Exception as ex:  # noqa: BLE001
        traceback.print_exc()
        try:
            ev.status, ev.note = "failed", f"{type(ex).__name__}: {ex}"
            db.commit()
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


def _worker():
    while True:
        process(_q.get())


def start_worker():
    """Start the background worker once, and pick up events received before a restart."""
    global _started
    if _started:
        return
    _started = True
    db = SessionLocal()
    try:
        for (eid,) in db.execute(select(Event.id).where(Event.status.in_(["received", "investigating"]))):
            db.get(Event, eid).status = "received"
            _q.put(eid)
        db.commit()
    finally:
        db.close()
    threading.Thread(target=_worker, daemon=True, name="aria-watch").start()


def lessons(db, org_id: str, rule_id: str, limit: int = 8) -> list[str]:
    """The feedback loop: how the area's owners decided earlier suggestions for this watch rule, newest first."""
    q = (select(Suggestion).join(Event, Event.id == Suggestion.event_id)
         .where(Suggestion.org_id == org_id, Event.matched_rule == rule_id, Suggestion.status != "pending")
         .order_by(Suggestion.decided_at.desc()).limit(limit))
    out = []
    for s in db.execute(q).scalars():
        verb = "rejected" if s.status == "rejected" else "approved"
        out.append(f"{s.decided_by or 'An owner'} {verb} \"{s.title}\"" + (f". Their note: {s.note}" if s.note else ""))
    return out


def decide(db, access: Access, s: Suggestion, approve: bool, note: str = "") -> Suggestion:
    """The area's owner decides. Approval hands the suggestion to Aria Executor; the approver is accountable."""
    if s.status != "pending":
        raise ValueError(f"This suggestion is already {s.status}")
    if not is_owner(access, s.owner_role):
        raise PermissionError(f"Only the {s.owner_role} role can decide this suggestion")
    s.decided_by, s.note, s.decided_at = access.actor_label, (note or "")[:2000], datetime.now(timezone.utc)
    if not approve:
        s.status = "rejected"
        audit.record(db, s.org_id, access.actor_label, "suggestion.rejected", s.id, {"note": note}, commit=False)
        db.commit()
        return s
    s.status = "approved"
    audit.record(db, s.org_id, access.actor_label, "suggestion.approved", s.id, {"note": note}, commit=False)
    p = plans.create(db, s.org_id, s.title, s.rationale, s.steps, source="watch", owner_role=s.owner_role, suggestion_id=s.id)
    p = plans.decide(db, access, p, True, note)
    s.plan_id = p.id
    s.status = "executed" if p.status == "executed" else "approved" if p.status == "escalated" else "failed"
    db.commit()
    return s
