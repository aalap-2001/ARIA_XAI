"""What each Studio layer is doing right now: read-only views over the organisation's own data, for the Studio tabs."""
from collections import Counter

from sqlalchemy import func, select

from . import audit, plans, studio
from .agents import ANALYST, EXECUTOR, WATCH
from .models import (AuditEntry, Blueprint, Conversation, DataConnection, Decision, Document, Event, Message, Organisation, Plan,
                     Suggestion, User)
from .rbac import Access
from .watch import lessons as watch_lessons


def _bp_live(db, org_id: str):
    return db.execute(select(Blueprint).where(Blueprint.org_id == org_id, Blueprint.status == "published")).scalar()


def _names(db, ids) -> dict:
    ids = {i for i in ids if i}
    return {u.id: u.name for u in db.execute(select(User).where(User.id.in_(ids))).scalars()} if ids else {}


def cognitive(db, a: Access, org: Organisation) -> dict:
    rows = db.execute(select(Decision).where(Decision.org_id == a.org_id).order_by(Decision.created_at.desc()).limit(500)).scalars().all()
    return {"verdicts": dict(Counter(d.verdict for d in rows)), "total": len(rows),
            "recent": [{"id": d.id, "action": d.action, "verdict": d.verdict, "effect": d.effect, "status": d.status,
                        "summary": (d.summary or "")[:240], "reasons": (d.reasons or [])[:3], "at": d.created_at} for d in rows[:8]]}


def motivation(db, a: Access, org: Organisation) -> dict:
    if not (a.can("approvals:view") and a.can_use_agent("watch")):
        return {"allowed": False}
    from .routers.govern import sug_out
    evs = db.execute(select(Event).where(Event.org_id == a.org_id).order_by(Event.received_at.desc()).limit(500)).scalars().all()
    sugs = db.execute(select(Suggestion).where(Suggestion.org_id == a.org_id).order_by(Suggestion.created_at.desc()).limit(30)).scalars().all()
    reviewed = db.execute(select(Decision).where(Decision.org_id == a.org_id, Decision.reviewer != "")
                          .order_by(Decision.updated_at.desc()).limit(8)).scalars().all()
    bp = _bp_live(db, a.org_id)
    rules = (bp.content.get("watch_rules") if bp else None) or []
    return {"allowed": True, "events": dict(Counter(e.status for e in evs)), "events_total": len(evs),
            "recent_events": [{"id": e.id, "type": e.type, "entity_id": e.entity_id, "status": e.status, "rule": e.matched_rule,
                               "note": (e.note or "")[:240], "at": e.received_at} for e in evs[:8]],
            "suggestions": [sug_out(s, a) for s in sugs],
            "feedback": [{"id": d.id, "action": d.action, "status": d.status, "reviewer": d.reviewer, "note": (d.review_note or "")[:300],
                          "at": d.updated_at} for d in reviewed],
            "learned": [{"rule": r["id"], "why": r.get("why", ""), "lessons": watch_lessons(db, a.org_id, r["id"], 3)} for r in rules]}


def knowledge(db, a: Access, org: Organisation) -> dict:
    docs = db.execute(select(Document).where(Document.org_id == a.org_id).order_by(Document.created_at.desc())).scalars().all()
    conns = db.execute(select(DataConnection).where(DataConnection.org_id == a.org_id)).scalars().all()
    bps = db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id).order_by(Blueprint.version.desc())).scalars().all()
    n_conv = db.scalar(select(func.count()).select_from(Conversation).where(Conversation.org_id == a.org_id)) or 0
    n_msg = db.scalar(select(func.count()).select_from(Message).join(Conversation, Conversation.id == Message.conversation_id)
                      .where(Conversation.org_id == a.org_id)) or 0
    n_dec = db.scalar(select(func.count()).select_from(Decision).where(Decision.org_id == a.org_id)) or 0
    n_ev = db.scalar(select(func.count()).select_from(Event).where(Event.org_id == a.org_id)) or 0
    live = next((b for b in bps if b.status == "published"), None)
    who = _names(db, [d.uploaded_by for d in docs] + [b.created_by for b in bps])
    n_tables = lambda c: len((c.schema_snapshot or {}).get("tables") or [])  # noqa: E731
    stores = [
        {"id": "documents", "name": "Documents", "kind": "Long-term knowledge", "count": len(docs),
         "detail": f"{sum(d.pages for d in docs)} pages in {sum(d.chunks for d in docs)} searchable passages",
         "how": "The original file is encrypted at rest. Its text is split into passages and indexed by term, so agents can find and cite the page."},
        {"id": "data", "name": "Business data", "kind": "Live facts", "count": len(conns), "detail": f"{sum(n_tables(c) for c in conns)} tables mapped",
         "how": "Aria XAI keeps a snapshot of the schema, never a copy of your rows. Agents read rows live and read-only, through the SQL guard."},
        {"id": "blueprint", "name": "Product understanding", "kind": "Semantic memory", "count": len(bps),
         "detail": f"live version {live.version}" if live else "no live version yet",
         "how": "What Aria XAI understood about your product: entities, facts, rules, agents and actions. Every change saves a new version and earlier ones are kept."},
        {"id": "conversations", "name": "Conversations", "kind": "Episodic memory", "count": n_conv, "detail": f"{n_msg} messages with their agent trace",
         "how": "Each conversation keeps its messages and the full trace of what the agents did, so the team can follow up and people can review it."},
        {"id": "decisions", "name": "Decisions", "kind": "Decision memory", "count": n_dec, "detail": "facts, verdict, approver and outcome",
         "how": "For every action: the facts the model stated, the rules' verdict, who approved it and what was carried out."},
        {"id": "events", "name": "Product events", "kind": "Observations", "count": n_ev, "detail": "reported by your product",
         "how": "Activity your product sends to Aria Watch, with what Aria Watch concluded about each one."},
    ]
    timeline = ([{"at": d.created_at, "store": "Documents", "text": f"Learned {d.filename} ({d.pages} pages, {d.chunks} passages)",
                  "by": who.get(d.uploaded_by, "")} for d in docs]
                + [{"at": c.introspected_at or c.created_at, "store": "Business data", "text": f"Mapped {c.name}: {n_tables(c)} tables", "by": ""}
                   for c in conns]
                + [{"at": b.created_at, "store": "Product understanding",
                    "text": f"Version {b.version} ({'live' if b.status == 'published' else b.status})" + (f": {b.note}" if b.note else ""),
                    "by": who.get(b.created_by, "Aria XAI")} for b in bps if b.status != "failed"])
    timeline.sort(key=lambda x: str(x["at"]), reverse=True)
    return {"stores": stores, "timeline": timeline[:14],
            "documents": [{"id": d.id, "filename": d.filename, "pages": d.pages, "chunks": d.chunks, "at": d.created_at} for d in docs[:12]],
            "connections": [{"id": c.id, "name": c.name, "kind": c.kind, "at": c.introspected_at,
                             "tables": [t.get("name") for t in (c.schema_snapshot or {}).get("tables") or []][:20]} for c in conns],
            "can_search": a.can("knowledge:view")}


def swarm(db, a: Access, org: Organisation) -> dict:
    bp = _bp_live(db, a.org_id)
    specialists = (bp.content.get("agents") if bp else None) or []
    names = {"aria": "Aria Orchestrator", ANALYST["id"]: ANALYST["name"], EXECUTOR["id"]: EXECUTOR["name"], WATCH["id"]: WATCH["name"],
             **{g["id"]: g["name"] for g in specialists}}
    nm = lambda x: names.get(x, x)  # noqa: E731
    rows = db.execute(select(Message, Conversation).join(Conversation, Conversation.id == Message.conversation_id)
                      .where(Conversation.org_id == a.org_id, Message.role == "assistant").order_by(Message.created_at.desc()).limit(60)).all()
    work, tools, runs = Counter(), Counter(), []
    for m, c in rows:
        route, steps = ["aria"], []
        work["aria"] += 1
        for t in m.trace or []:
            if t.get("type") == "delegate":
                to = t.get("to")
                work[to] += 1
                if to not in route:
                    route.append(to)
                steps.append(f"{nm(t.get('agent'))} handed to {nm(to)}: {str(t.get('task', ''))[:140]}")
            elif t.get("type") == "tool_call":
                tools[t.get("tool")] += 1
                steps.append(f"{nm(t.get('agent'))} used {t.get('tool')}")
        if len(runs) < 8:
            mine = c.channel != "console" or c.user_id == a.actor_id
            runs.append({"id": m.id, "conversation_id": c.id if mine else None, "title": c.title if mine else "A colleague's conversation",
                         "channel": c.channel, "at": m.created_at, "route": [nm(r) for r in route], "steps": steps[:8]})
    pls = db.execute(select(Plan).where(Plan.org_id == a.org_id).order_by(Plan.created_at.desc()).limit(10)).scalars().all()
    keep = ("id", "title", "summary", "status", "source", "owner_role", "accountable", "created_at")
    return {"leads": [{"id": g["id"], "name": g["name"], "purpose": g["purpose"]} for g in (ANALYST, EXECUTOR, WATCH)],
            "specialists": [{"id": g["id"], "name": g["name"], "purpose": g.get("purpose", ""), "tools": g.get("tools", [])} for g in specialists],
            "workload": {nm(k): v for k, v in work.most_common()}, "tools": dict(tools.most_common(8)), "runs": runs,
            "plans": [{k: v for k, v in plans.out(p).items() if k in keep} | {"steps": len(p.steps or [])} for p in pls]}


def interface(db, a: Access, org: Organisation) -> dict:
    rows = db.execute(select(Conversation.channel, func.count()).where(Conversation.org_id == a.org_id).group_by(Conversation.channel)).all()
    return {"persona": studio.persona(org), "channels": {ch: n for ch, n in rows}}


def governance(db, a: Access, org: Organisation) -> dict:
    rows = db.execute(select(Decision).where(Decision.org_id == a.org_id)).scalars().all()
    out = {"effects": dict(Counter(d.effect for d in rows)), "statuses": dict(Counter(d.status for d in rows)), "total": len(rows),
           "pending_plans": db.scalar(select(func.count()).select_from(Plan).where(Plan.org_id == a.org_id, Plan.status == "awaiting_approval")) or 0,
           "audit": None}
    if a.can("audit:view"):
        entries = db.execute(select(AuditEntry).where(AuditEntry.org_id == a.org_id).order_by(AuditEntry.seq.desc()).limit(12)).scalars().all()
        out["audit"] = {"verify": audit.verify(db, a.org_id),
                        "recent": [{"seq": e.seq, "at": e.at, "actor": e.actor, "kind": e.kind, "target": e.target} for e in entries]}
    return out


LIVE = {"cognitive": cognitive, "motivation": motivation, "knowledge": knowledge, "swarm": swarm, "interface": interface,
        "governance": governance}
