"""The neuro-symbolic decision path, with a human accountable for every action.

    LLM (neural) establishes facts and proposes an action inside a plan
      → the responsible human approves the plan            (accountability: that person, never the AI)
      → Rule Engine (symbolic): soft signals → gate → hard rules → VALID / INVALID / INSUFFICIENT_EVIDENCE
      → Sentinel policy against the ACCOUNTABLE PERSON'S authority: their role's allowed actions, approval limit and
        clearance for high-risk actions → ALLOW / REVIEW (escalate to the area's owner role) / BLOCK
      → ALLOW executes the action's executor: a signed webhook, or one declared database INSERT/UPDATE.
Every step is written to the audit chain with the accountable person as the actor.
"""
import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from ariax.core.ids import canonical, sha256
from ariax.rules import RuleEngine

from . import audit
from . import blueprint as BP
from .config import WEBHOOK_TIMEOUT
from .datasources import DataError, _check_host, write_row
from .models import Blueprint, DataConnection, Decision, EgressLog, Organisation
from .rbac import Access
from .security import decrypt_json, sign

ENGINE = RuleEngine()


def evaluate(content: dict, action: str, facts: dict, version: int, evidence: dict | None = None) -> dict:
    """check_rules: the symbolic verdict without requesting anything.

    The explanation has the four parts an auditor needs: extraction (which source produced each fact, at what
    confidence), soft (how evidence was combined), gate (which threshold turned scores into booleans) and hard
    (which cited rules passed or failed)."""
    evidence = {k: v for k, v in (evidence or {}).items() if isinstance(v, dict)}
    ex = ENGINE.evaluate(BP.engine_rules(content, action), {"facts": facts, "evidence": evidence}, f"blueprint v{version}")
    ex["action"] = action
    ex["extraction"] = [{"fact": k, "value": v, "source": (evidence.get(k) or {}).get("source") or "not stated",
                         "confidence": (evidence.get(k) or {}).get("confidence")} for k, v in (facts or {}).items()]
    return ex


def kill_switch(db, org_id: str) -> dict | None:
    """The organisation's kill switch, if it is on. While on, nothing above LOW risk is decided ALLOW or sent."""
    ks = (db.get(Organisation, org_id).settings or {}).get("kill_switch") or {}
    return ks if ks.get("active") else None


def is_owner(access: Access, owner_role: str | None) -> bool:
    return "*" in access.permissions or (bool(owner_role) and access.role_name == owner_role)


def authority(access: Access | None, a: dict, amount) -> dict:
    """What the accountable person may approve on their own, for display and for the policy."""
    if access is None:
        return {"who": None, "within": False, "reasons": ["No person approved this request"]}
    reasons, within = [], True
    lim = access.approval_limit
    if not access.can_action(a["name"]):
        within = False
        reasons.append(f"Your role ({access.role_name}) may not request {a['name']}")
    if amount is not None and lim is not None and float(amount) > lim:
        within = False
        reasons.append(f"Amount {amount:g} is above your approval limit of {lim:g}")
    if a["risk"] == "HIGH" and not (access.can("approvals:approve") or is_owner(access, a.get("owner_role"))):
        within = False
        reasons.append(f"HIGH-risk actions need someone with approval authority ({a.get('owner_role')})")
    if a.get("always_review") and not is_owner(access, a.get("owner_role")):
        within = False
        reasons.append(f"{a['name']} always needs the {a.get('owner_role')} role's approval")
    return {"who": access.actor_label, "role": access.role_name, "limit": lim, "within": within,
            "reasons": reasons or [f"Within {access.actor_label}'s authority as {access.role_name}"]}


def _policy(a: dict, verdict: str, amount, explanation, accountable: Access | None) -> tuple[str, list[str]]:
    failing = [h for h in explanation["hard"] if h["status"] not in ("PASS", "NOT_APPLICABLE")]
    if accountable is not None and not accountable.can_action(a["name"]):
        # Outside the person's role entirely: Aria Executor may not do it for them, and nobody is asked to override it.
        return "BLOCK", [f"{accountable.actor_label}'s role ({accountable.role_name}) is not permitted to {a['name']}"]
    if verdict == "INVALID":
        return "BLOCK", [f"Rule '{h['id']}' failed: {h.get('message') or h['description']}" for h in failing if h["status"] == "INVALID"]
    if verdict == "INSUFFICIENT_EVIDENCE":
        return "REVIEW", [f"Not enough evidence ({', '.join(h['id'] for h in failing)}), escalated to {a.get('owner_role')}"]
    if accountable is None:  # API / widget request with no human approving: only clearly safe things run
        if a["risk"] == "LOW":
            return "ALLOW", ["Rules passed and the action is low risk"]
        lim = a.get("auto_approve_below")
        if lim is not None and amount is not None and float(amount) < float(lim) and not a.get("always_review"):
            return "ALLOW", [f"Rules passed and amount {amount:g} is below the automatic limit {lim:g}"]
        return "REVIEW", [f"No person approved this {a['risk']} risk request, escalated to {a.get('owner_role')}"]
    auth = authority(accountable, a, amount)
    if not auth["within"]:
        return "REVIEW", auth["reasons"] + [f"Escalated to {a.get('owner_role')}"]
    return "ALLOW", [f"Rules passed; approved by {accountable.actor_label} ({accountable.role_name}) within their authority"]


def propose(db, requester: Access, bp: Blueprint, agent_id: str, action_name: str, facts: dict, payload: dict, summary: str,
            conversation_id: str | None, accountable: Access | None = None, plan_id: str | None = None,
            evidence: dict | None = None) -> Decision:
    content = bp.content
    a = next((x for x in content.get("actions", []) if x["name"] == action_name), None)
    facts = facts or {}
    amount = None
    if a and a.get("amount_fact") and facts.get(a["amount_fact"]) not in (None, ""):
        try:
            amount = float(facts[a["amount_fact"]])
        except (TypeError, ValueError):
            amount = None
    explanation, verdict = {}, "INVALID"
    if not a:
        effect, reasons, risk = "BLOCK", [f"Action '{action_name}' is not defined in the published blueprint (default deny)"], "HIGH"
    elif not requester.can_action(action_name):
        effect, reasons, risk = "BLOCK", [f"The requester's role ({requester.role_name}) may not request {action_name}"], a["risk"]
    else:
        risk = a["risk"]
        missing = [f for f in a.get("required_facts", []) if facts.get(f) in (None, "")]
        explanation = evaluate(content, action_name, facts, bp.version, evidence)
        verdict = explanation["verdict"]
        if missing and verdict == "VALID":
            verdict = "INSUFFICIENT_EVIDENCE"
        effect, reasons = _policy(a, verdict, amount, explanation, accountable)
        ks = kill_switch(db, requester.org_id)
        if ks and risk != "LOW":
            effect, reasons = "BLOCK", [f"Kill switch is on ({ks.get('reason') or 'no reason given'}): {risk} risk actions are halted"]
        if missing:
            reasons.append("Missing required facts: " + ", ".join(missing))
    status = {"ALLOW": "APPROVED", "REVIEW": "PENDING_REVIEW", "BLOCK": "BLOCKED"}[effect]
    who = accountable.actor_label if accountable else None
    d = Decision(org_id=requester.org_id, conversation_id=conversation_id, blueprint_version=bp.version, agent=agent_id, action=action_name,
                 risk=risk, summary=(summary or "")[:2000], facts=facts, payload=payload or {}, payload_hash=sha256(canonical(payload or {})),
                 amount=amount, verdict=verdict, explanation=explanation, effect=effect, reasons=reasons, status=status,
                 requested_by=requester.actor_label, accountable=who, owner_role=(a or {}).get("owner_role"), plan_id=plan_id)
    db.add(d)
    db.flush()
    audit.record(db, requester.org_id, who or requester.actor_label, "decision.made", d.id,
                 {"action": action_name, "agent": agent_id, "verdict": verdict, "effect": effect, "amount": amount,
                  "accountable": who, "plan_id": plan_id}, commit=False)
    if effect == "ALLOW":
        execute(db, d, a, who or "policy")
    db.commit()
    return d


def execute(db, d: Decision, action: dict | None, approved_by: str):
    """Carry out an approved decision through the action's executor."""
    ex = (action or {}).get("executor") or {"type": "webhook", "url": (action or {}).get("webhook_url", "")}
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ks = kill_switch(db, d.org_id)
    if ks and d.risk != "LOW":  # checked again at the moment of egress: an approval cannot outrun the kill switch
        d.status, d.execution = "BLOCKED", {"note": "Kill switch is on: nothing was sent.", "approved_by": approved_by, "at": at}
        d.updated_at = datetime.now(timezone.utc)
        audit.record(db, d.org_id, approved_by, "decision.halted", d.id, {"action": d.action, "reason": "kill switch"}, commit=False)
        return
    values = {**(d.facts or {}), **(d.payload or {})}
    if ex.get("type") == "database":
        conn = db.get(DataConnection, ex.get("connection_id"))
        try:
            if not conn or conn.org_id != d.org_id:
                raise DataError("The action's data connection no longer exists")
            _egress(db, d, "database", f"{conn.name}.{ex.get('table')}")
            res = write_row(conn, ex, values)
            d.status, d.execution = "EXECUTED", {"executor": "database", "connection": conn.name, **res, "approved_by": approved_by, "at": at}
        except DataError as e:
            d.status, d.execution = "FAILED", {"executor": "database", "error": str(e), "approved_by": approved_by, "at": at}
    elif not ex.get("url"):
        d.status, d.execution = "EXECUTED", {"executor": "none", "note": "No webhook configured for this action, the decision is recorded only.",
                                             "approved_by": approved_by, "at": at}
    else:
        url = ex["url"]
        org = db.get(Organisation, d.org_id)
        secret = decrypt_json(org.webhook_secret_enc).get("secret", "")
        body = json.dumps({"decision_id": d.id, "action": d.action, "payload": d.payload, "facts": d.facts, "verdict": d.verdict,
                           "accountable": d.accountable, "approved_by": approved_by, "agent": d.agent,
                           "blueprint_version": d.blueprint_version}, default=str).encode()
        try:
            _check_host(urlparse(url).hostname or "")
            _egress(db, d, "webhook", url)
            r = httpx.post(url, content=body, timeout=WEBHOOK_TIMEOUT, headers={
                "Content-Type": "application/json", "User-Agent": "AriaX-Webhook/1.0", "X-AriaX-Decision": d.id,
                "X-AriaX-Signature": sign(body, secret)})
            ok = 200 <= r.status_code < 300
            d.status = "EXECUTED" if ok else "FAILED"
            d.execution = {"executor": "webhook", "url": url, "status_code": r.status_code, "response": r.text[:500], "approved_by": approved_by, "at": at}
        except (httpx.HTTPError, DataError) as e:
            d.status = "FAILED"
            d.execution = {"executor": "webhook", "url": url, "error": f"{type(e).__name__}: {str(e)[:300]}", "approved_by": approved_by, "at": at}
    d.updated_at = datetime.now(timezone.utc)
    audit.record(db, d.org_id, approved_by, "decision.executed", d.id, {"status": d.status, "action": d.action,
                                                                         "executor": ex.get("type"), "accountable": d.accountable}, commit=False)


def _egress(db, d: Decision, executor: str, target: str):
    """Write the send to the egress log before it leaves. The watchdog compares this log with the decisions."""
    db.add(EgressLog(org_id=d.org_id, decision_id=d.id, executor=executor, target=target[:500], payload_hash=d.payload_hash))
    db.flush()


def watchdog(db, org_id: str) -> dict:
    """Reconcile what was sent with what was approved. Anything sent without an approved decision is an incident."""
    incidents = []
    sent = db.execute(select(EgressLog).where(EgressLog.org_id == org_id).order_by(EgressLog.id)).scalars().all()
    for e in sent:
        d = db.get(Decision, e.decision_id) if e.decision_id else None
        if not d or d.org_id != org_id:
            incidents.append({"egress_id": e.id, "target": e.target, "at": e.at, "issue": "sent without a decision"})
        elif not (d.effect == "ALLOW" or d.reviewer) or d.status in ("REJECTED", "PENDING_REVIEW", "BLOCKED"):
            incidents.append({"egress_id": e.id, "decision_id": d.id, "target": e.target, "at": e.at, "issue": f"sent although the decision is {d.status.lower()}"})
        elif e.payload_hash != d.payload_hash:
            incidents.append({"egress_id": e.id, "decision_id": d.id, "target": e.target, "at": e.at, "issue": "payload differs from what was approved"})
    logged = {e.decision_id for e in sent}
    for d in db.execute(select(Decision).where(Decision.org_id == org_id, Decision.status.in_(["EXECUTED", "FAILED"]))).scalars():
        if (d.execution or {}).get("executor") in ("webhook", "database") and d.id not in logged:
            incidents.append({"decision_id": d.id, "issue": "executed but the send was never logged"})
    return {"ok": not incidents, "checked": len(sent), "incidents": incidents}


def review(db, access: Access, d: Decision, approve: bool, note: str):
    """An escalation is decided by the area's owner role, within their approval limit. They become accountable."""
    if d.status != "PENDING_REVIEW":
        raise ValueError(f"This decision is {d.status.replace('_', ' ').lower()}, not waiting for review")
    if not is_owner(access, d.owner_role) and not (not d.owner_role and access.can("approvals:approve")):
        raise PermissionError(f"Only the {d.owner_role} role can decide this escalation")
    lim = access.approval_limit
    if approve and lim is not None and (d.amount or 0) > lim:
        raise PermissionError(f"Your approval limit is {lim:g}; this request is for {d.amount:g}")
    d.reviewer, d.review_note, d.updated_at = access.actor_label, (note or "")[:2000], datetime.now(timezone.utc)
    audit.record(db, d.org_id, access.actor_label, "decision.reviewed", d.id, {"approve": approve, "note": note}, commit=False)
    if approve:
        d.accountable = access.actor_label
        bp = db.execute(select(Blueprint).where(Blueprint.org_id == d.org_id, Blueprint.version == d.blueprint_version)).scalar()
        action = next((x for x in (bp.content if bp else {}).get("actions", []) if x["name"] == d.action), None)
        execute(db, d, action, access.actor_label)
    else:
        d.status = "REJECTED"
    db.commit()
    return d
