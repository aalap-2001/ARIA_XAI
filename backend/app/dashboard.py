"""The Command Centre: what the signed-in person needs from Aria XAI today. What needs them, what the AI team is doing, what it
delivered, and how healthy and costly it is. Everything is computed from the organisation's own records and the person's role."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from . import decisions, plans, studio
from .agents import ANALYST, EXECUTOR, WATCH
from .models import Blueprint, Conversation, Decision, Event, Message, Organisation, Plan, Suggestion, UsageEvent
from .rbac import Access

DAYS = 30


def _utc(d):
    if d is None:
        return None
    if isinstance(d, str):
        d = datetime.fromisoformat(d)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def build(db, a: Access) -> dict:
    now = datetime.now(timezone.utc)
    since, week = now - timedelta(days=30), now - timedelta(days=7)
    org = db.get(Organisation, a.org_id)
    bp = db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id, Blueprint.status == "published")).scalar()
    content = bp.content if bp else {}
    sees_all = a.can("audit:view") or a.can("approvals:approve")

    # ---- records this person may see
    dq = select(Decision).where(Decision.org_id == a.org_id)
    if not sees_all:
        dq = dq.where(Decision.requested_by == a.actor_label)
    decs = db.execute(dq.order_by(Decision.created_at.desc()).limit(1000)).scalars().all() if a.can("approvals:view") else []
    pls = [p for p in db.execute(select(Plan).where(Plan.org_id == a.org_id).order_by(Plan.created_at.desc()).limit(300)).scalars()
           if p.approver_user_id == a.actor_id or plans.can_decide(a, p) or a.can("audit:view")]
    watch_ok = a.can("approvals:view") and a.can_use_agent("watch")
    sugs = db.execute(select(Suggestion).where(Suggestion.org_id == a.org_id).order_by(Suggestion.created_at.desc()).limit(300)).scalars().all() if watch_ok else []
    evs = db.execute(select(Event).where(Event.org_id == a.org_id, Event.received_at >= since).order_by(Event.received_at.desc())).scalars().all() if watch_ok else []
    msgs = db.execute(select(Message, Conversation).join(Conversation, Conversation.id == Message.conversation_id)
                      .where(Conversation.org_id == a.org_id, Message.role == "assistant", Message.created_at >= now - timedelta(days=DAYS + 1))
                      .order_by(Message.created_at.desc())).all()

    # ---- needs your attention
    attention = []
    for d in decs:
        if d.status == "PENDING_REVIEW" and a.can("approvals:approve") and decisions.is_owner(a, d.owner_role):
            attention.append({"kind": "Approval", "title": d.summary or d.action, "detail": f"{d.action}, {d.risk.lower()} risk"
                              + (f", {d.amount:g}" if d.amount else "") + f", requested by {d.requested_by}", "at": d.created_at,
                              "to": f"/approvals/{d.id}", "tone": "warn"})
    for p in pls:
        if p.status == "awaiting_approval" and plans.can_decide(a, p):
            attention.append({"kind": "Plan to approve", "title": p.title, "detail": f"{len(p.steps or [])} step(s) proposed by "
                              + ("Aria Watch" if p.source == "watch" else "Aria Executor") + ". Nothing runs until you approve.",
                              "at": p.created_at, "to": f"/chat/{p.conversation_id}" if p.conversation_id else "/approvals", "tone": "warn"})
    for s in sugs:
        if s.status == "pending" and a.can("approvals:approve") and decisions.is_owner(a, s.owner_role):
            attention.append({"kind": "Suggestion", "title": s.title, "detail": s.benefit or s.rationale, "at": s.created_at,
                              "to": "/activity", "tone": "accent"})
    for d in decs:
        if d.status in ("FAILED",) and _utc(d.updated_at) >= week:
            attention.append({"kind": "Failed", "title": d.summary or d.action, "detail": "The approved action could not be carried out.",
                              "at": d.updated_at, "to": f"/approvals/{d.id}", "tone": "bad"})
    attention.sort(key=lambda x: str(x["at"]), reverse=True)

    # ---- the AI workforce
    names = {"aria": "Aria Orchestrator", ANALYST["id"]: ANALYST["name"], EXECUTOR["id"]: EXECUTOR["name"],
             **{g["id"]: g["name"] for g in content.get("agents") or []}}
    work, last = Counter(), {}
    per_day = defaultdict(lambda: Counter())
    for m, c in msgs:
        at = _utc(m.created_at)
        per_day[at.date().isoformat()]["requests"] += 1
        involved = {"aria"} | {t.get("to") for t in m.trace or [] if t.get("type") == "delegate"}
        for g in involved:
            if g:
                work[g] += 1
                last[g] = max(last.get(g, at), at)
    for e in evs:
        if e.status not in ("ignored", "received"):
            work["watch"] += 1
            last["watch"] = max(last.get("watch", _utc(e.received_at)), _utc(e.received_at))
    persona = studio.persona(org)
    team = ([{"id": "aria", "name": "Aria Orchestrator", "role": f"Speaks to people as {persona['name']}", "kind": "lead"}]
            + [{"id": g["id"], "name": g["name"], "role": g["purpose"], "kind": "lead"} for g in (ANALYST, EXECUTOR)]
            + ([{"id": "watch", "name": WATCH["name"], "role": WATCH["purpose"], "kind": "lead"}] if watch_ok else [])
            + [{"id": g["id"], "name": g["name"], "role": g.get("purpose", ""), "kind": "specialist"} for g in content.get("agents") or []])
    for g in team:
        seen = last.get(g["id"])
        g["work"] = work.get(g["id"], 0)
        g["last"] = seen
        g["status"] = "active" if seen and seen >= now - timedelta(days=1) else "recent" if seen and seen >= since else "idle"

    # ---- outcomes and performance
    recent = [d for d in decs if _utc(d.created_at) >= since]
    done = [d for d in recent if d.status == "EXECUTED"]
    by_action = defaultdict(lambda: {"count": 0, "amount": 0.0})
    for d in done:
        by_action[d.action]["count"] += 1
        by_action[d.action]["amount"] += d.amount or 0
    for d in decs:
        day = _utc(d.created_at).date().isoformat()
        per_day[day]["decisions"] += 1
        if d.status == "EXECUTED":
            per_day[day]["completed"] += 1
    effects = Counter(d.effect for d in recent)
    reviewed = [d for d in decs if d.reviewer]
    exceptions = sum(1 for d in recent if d.status in ("BLOCKED", "FAILED")) + sum(1 for e in evs if e.status == "failed") \
        + sum(1 for p in pls if p.status == "failed" and _utc(p.created_at) >= since)
    in_progress = sum(1 for p in pls if p.status in ("awaiting_approval", "escalated")) + sum(1 for e in evs if e.status == "investigating") \
        + sum(1 for d in decs if d.status == "PENDING_REVIEW")
    pct = lambda n, t: round(100 * n / t) if t else None  # noqa: E731

    usage = None
    if a.can("usage:view"):
        u = db.execute(select(func.count(), func.coalesce(func.sum(UsageEvent.input_tokens + UsageEvent.output_tokens), 0),
                              func.coalesce(func.avg(UsageEvent.latency_ms), 0))
                       .where(UsageEvent.org_id == a.org_id, UsageEvent.at >= since)).one()
        usage = {"calls": u[0], "tokens": int(u[1]), "avg_ms": int(u[2] or 0)}

    # ---- what happened lately
    feed = []
    for d in decs[:15]:
        feed.append({"at": d.created_at, "who": names.get(d.agent, d.agent) if d.agent else "Aria Executor", "text": f"{d.action}: {d.summary}".strip(": "),
                     "state": d.status, "to": f"/approvals/{d.id}"})
    for p in pls[:10]:
        feed.append({"at": p.decided_at or p.created_at, "who": "Aria Watch" if p.source == "watch" else "Aria Executor",
                     "text": f"Plan: {p.title}", "state": p.status, "to": f"/chat/{p.conversation_id}" if p.conversation_id else None})
    for s in sugs[:8]:
        feed.append({"at": s.created_at, "who": "Aria Watch", "text": f"Suggested: {s.title}", "state": s.status, "to": "/activity"})
    for m, c in msgs[:15]:
        mine = c.channel != "console" or c.user_id == a.actor_id
        route = ["aria"] + [t.get("to") for t in m.trace or [] if t.get("type") == "delegate"]
        feed.append({"at": m.created_at, "who": " and ".join(dict.fromkeys(names.get(r, r) for r in route if r)),
                     "text": f"Answered: {c.title}" if mine else "Answered a colleague's request", "state": "answered",
                     "to": f"/chat/{c.id}" if mine and c.channel == "console" else None})
    feed.sort(key=lambda x: str(x["at"]), reverse=True)

    days = [(now - timedelta(days=i)).date().isoformat() for i in range(DAYS - 1, -1, -1)]
    my_convs = db.scalar(select(func.count()).select_from(Conversation).where(Conversation.org_id == a.org_id, Conversation.user_id == a.actor_id)) or 0
    return {
        "persona": persona, "org": org.name, "blueprint": {"version": bp.version, "industry": content.get("industry")} if bp else None,
        "kpis": {"attention": len(attention), "in_progress": in_progress, "completed": len(done),
                 "value": round(sum(d.amount or 0 for d in done), 2), "exceptions": exceptions,
                 "auto_rate": pct(effects.get("ALLOW", 0), len(recent)), "pass_rate": pct(sum(1 for d in recent if d.verdict == "VALID"), len(recent)),
                 "approval_rate": pct(sum(1 for d in reviewed if d.status != "REJECTED"), len(reviewed)), "decisions": len(recent),
                 "team": len(team), "active_agents": sum(1 for g in team if g["status"] != "idle")},
        "attention": attention[:8], "team": team, "feed": feed[:14],
        "series": [{"day": d, **{k: per_day[d][k] for k in ("requests", "decisions", "completed")}} for d in days],
        "outcomes": sorted(({"action": k, **v} for k, v in by_action.items()), key=lambda x: -x["count"])[:6],
        "goals": [{"name": k.get("name"), "description": k.get("description", "")} for k in content.get("kpis") or []][:4],
        "usage": usage, "mine": {"conversations": my_convs},
        "sees": {"decisions": a.can("approvals:view"), "all": sees_all, "watch": watch_ok},
    }
