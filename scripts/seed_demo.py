"""Create the Aria XAI demo businesses and demo logins.

    python scripts/seed_demo.py            add anything missing (safe to run again)
    python scripts/seed_demo.py --reset    delete the synthetic demo businesses and create them again

What it creates (all synthetic, see scripts/demo_data.py):
  * three fully set-up businesses for the demo owner (demo.owner@example.com), each with documents, a connected database,
    a published blueprint with later edits by people, a team in every role, weeks of agent-team history, approvals,
    Aria Watch events and suggestions, API keys and a valid hash-chained audit log
  * a second demo login (demo.onboarding@example.com) with its own copy of Northwind Rentals (demo) as it is: mid-setup

Everything is created through the product's own code paths (rule engine, plans, decisions, Aria Watch, Studio), so every
verdict, escalation and database write is real. Only timestamps are moved back so the history spans the past weeks.
"""
import copy
import hashlib
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT), str(ROOT / "scripts")]

from sqlalchemy import select  # noqa: E402

from app import audit, decisions, knowledge, plans, studio, watch  # noqa: E402
from app import blueprint as BP  # noqa: E402
from app.config import DATA_DIR  # noqa: E402
from app.datasources import introspect, upload_path  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.models import (ApiKey, AuditEntry, Blueprint, Chunk, Conversation, DataConnection, Decision, Document, Event,  # noqa: E402
                        Membership, Message, Organisation, Plan, Role, Suggestion, User)
from app.rbac import Access  # noqa: E402
from app.routers.auth import create_org  # noqa: E402
from app.routers.product import save_version  # noqa: E402
from app.security import encrypt_bytes, new_token, sha  # noqa: E402
from ariax.core.ids import canonical, sha256  # noqa: E402
from demo_data import BUSINESSES as _CORE  # noqa: E402
from demo_verticals import PERSONAS as _VPERSONAS, VERTICALS  # noqa: E402

BUSINESSES = _CORE + VERTICALS

DEMO_OWNER = "demo.owner@example.com"
ONBOARDING = "demo.onboarding@example.com"
# The demo password is kept only as a salted scrypt hash (one-way); the plain text is not stored in any file.
PASSWORD_HASH = "scrypt$16384$8$1$3cLgWWbRHW4nCz4rhVrVoA==$5meoXsOuXxl9+BhUzscTXiPR8EFoHERf27I9csSA4sM="
if os.environ.get("ARIAX_DEMO_PASSWORD"):  # e.g. a Codespace: whoever runs it chooses (or is given) their own demo password
    from app.security import hash_password  # noqa: E402
    PASSWORD_HASH = hash_password(os.environ["ARIAX_DEMO_PASSWORD"])
ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@example.com"
NORTHWIND = "Northwind Rentals (demo)"
MODEL_GROUP = "demo-businesses"
NOW = datetime.now(timezone.utc).replace(microsecond=0)


# ------------------------------------------------------------------ helpers
def access_for(db, org_id: str, user: User) -> Access:
    m = db.execute(select(Membership).where(Membership.org_id == org_id, Membership.user_id == user.id)).scalar()
    return Access(org_id=org_id, actor_id=user.id, actor_label=user.email, role_id=m.role.id, role_name=m.role.name,
                  permissions=m.role.permissions, scopes=m.role.scopes, via="session")


class Clock:
    """Moves what the last step wrote (audit entries and rows) to a point in the past."""

    def __init__(self, db, org_id):
        self.db, self.org_id = db, org_id
        self.seq = db.execute(select(AuditEntry.seq).where(AuditEntry.org_id == org_id).order_by(AuditEntry.seq.desc()).limit(1)).scalar() or 0

    def stamp(self, when: datetime, *rows):
        self.db.flush()
        new = self.db.execute(select(AuditEntry).where(AuditEntry.org_id == self.org_id, AuditEntry.seq > self.seq)
                              .order_by(AuditEntry.seq)).scalars().all()
        for i, e in enumerate(new):
            e.at = (when + timedelta(seconds=20 * i)).isoformat(timespec="seconds")
            self.seq = e.seq
        for r in rows:
            for f in ("created_at", "updated_at", "received_at", "decided_at", "published_at", "introspected_at"):
                if hasattr(r, f) and (f in ("created_at", "updated_at", "received_at") or getattr(r, f) is not None):
                    setattr(r, f, when)
        self.db.commit()


def rechain(db, org_id: str):
    """Recompute the audit hash chain after timestamps were moved (only ever on a freshly seeded demo organisation)."""
    prev = audit.GENESIS
    for e in db.execute(select(AuditEntry).where(AuditEntry.org_id == org_id).order_by(AuditEntry.seq)).scalars():
        body = {"org_id": e.org_id, "at": e.at, "actor": e.actor, "kind": e.kind, "target": e.target, "detail": e.detail}
        e.prev_hash, e.hash = prev, sha256(prev + canonical(body))
        prev = e.hash
    db.commit()


def user(db, email: str, name: str) -> User:
    u = db.execute(select(User).where(User.email == email)).scalar()
    if not u:
        u = User(email=email, name=name, password_hash=PASSWORD_HASH)
        db.add(u)
        db.flush()
    return u


def ago(days: float, hour: int = 10) -> datetime:
    return (NOW - timedelta(days=days)).replace(hour=hour, minute=(int(days * 37) % 50) + 5, second=0)


def with_db(obj, conn_id: str):
    if isinstance(obj, dict):
        return {k: with_db(v, conn_id) for k, v in obj.items()}
    if isinstance(obj, list):
        return [with_db(v, conn_id) for v in obj]
    return conn_id if obj == "$DB" else obj


def md_table(cols, rows) -> str:
    if not rows:
        return "(none)"
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows]
    return "\n".join(out)


# ------------------------------------------------------------------ one business
def seed_business(db, spec: dict, owner: User):
    org, roles = create_org(db, spec["name"])
    org.product_description = spec["description"]
    org.settings = {**(org.settings or {}), "model_group": MODEL_GROUP}  # the demo businesses share one AI model
    db.add(Membership(org_id=org.id, user_id=owner.id, role_id=roles["Owner"].id))
    people = {}
    for name, local, role in spec["people"]:
        u = user(db, f"{local}@{spec['domain']}", name)
        db.add(Membership(org_id=org.id, user_id=u.id, role_id=roles[role].id))
        people[local] = u
    db.flush()
    clock = Clock(db, org.id)
    audit.record(db, org.id, owner.email, "org.created", org.id, {"name": org.name}, commit=False)
    for local, u in people.items():
        audit.record(db, org.id, owner.email, "user.invited", u.email, {"role": next(r for n, lo, r in spec["people"] if lo == local)}, commit=False)
    clock.stamp(ago(30, 9), org, *db.execute(select(Membership).where(Membership.org_id == org.id)).scalars().all())
    admin = next(u for lo, u in people.items() if next(r for n, l2, r in spec["people"] if l2 == lo) == "Org admin")
    builder = next(u for lo, u in people.items() if next(r for n, l2, r in spec["people"] if l2 == lo) == "Builder")

    # documents: originals kept (encrypted), text indexed for the agents
    for i, (fname, text) in enumerate(spec["documents"].items()):
        data = text.encode()
        d = Document(org_id=org.id, filename=fname, mime="text/markdown", size=len(data), sha256=hashlib.sha256(data).hexdigest(), uploaded_by=builder.id)
        db.add(d)
        db.flush()
        p = DATA_DIR / "orgs" / org.id / "documents" / f"{d.id}.bin"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(encrypt_bytes(data))
        knowledge.ingest(db, d, data)
        audit.record(db, org.id, builder.email, "knowledge.uploaded", fname, {"status": d.status, "chunks": d.chunks}, commit=False)
        clock.stamp(ago(29, 10 + i), d)

    # the connected database (writes enabled, so approved actions really change it)
    dbs = spec["database"]
    conn = DataConnection(org_id=org.id, name=dbs["name"], kind="upload", config={"filename": "demo.sqlite", "allow_writes": True})
    db.add(conn)
    db.flush()
    path = upload_path(conn)
    if path.exists():
        path.unlink()
    s = sqlite3.connect(path)
    for t, (cols, rows) in dbs["tables"].items():
        key = dbs.get("key", {}).get(t)
        defs = ", ".join(f'"{c}"' + (" INTEGER PRIMARY KEY AUTOINCREMENT" if c == key else "") for c in cols)
        s.execute(f'CREATE TABLE "{t}" ({defs})')
        s.executemany(f'INSERT INTO "{t}" VALUES ({", ".join("?" * len(cols))})', rows)
    s.commit()
    s.close()
    conn.schema_snapshot, conn.status, conn.introspected_at = introspect(conn), "ready", NOW
    audit.record(db, org.id, admin.email, "data.connected", conn.name, {"kind": "upload", "tables": len(dbs["tables"])}, commit=False)
    audit.record(db, org.id, admin.email, "data.writes_enabled", conn.name, {}, commit=False)
    clock.stamp(ago(29, 14), conn)

    # Aria XAI's understanding (version 1), then reviewed and published
    content = BP.normalise(with_db(copy.deepcopy(spec["content"]), conn.id))
    from app import understanding
    val = BP.validate(content, understanding.connections_index(db, org.id), understanding.role_names(db, org.id))
    n_chunks = db.execute(select(Chunk).where(Chunk.org_id == org.id)).scalars().all()
    v1 = Blueprint(org_id=org.id, version=1, status="draft", content=content, validation=val, created_by=admin.id,
                   note="Understood from description, documents and data",
                   sources={"described": True, "documents": list(spec["documents"]), "connections": [conn.name]},
                   progress=[{"step": s_, "state": "done"} for s_ in [
                       "Read the product description", f"Read {len(spec['documents'])} documents ({len(n_chunks)} passages)",
                       f"Read the schema of {conn.name} ({len(dbs['tables'])} tables)", "Proposed the agent team, rules and actions",
                       "Symbolic check: " + ("passed" if val["ok"] else f"{len(val['errors'])} error(s)")]])
    db.add(v1)
    db.flush()
    audit.record(db, org.id, "Aria XAI", "blueprint.generated", v1.id, {"version": 1, "industry": content.get("industry"), "errors": len(val["errors"])}, commit=False)
    clock.stamp(ago(28, 11), v1)
    if not val["ok"]:
        raise SystemExit(f"{spec['name']}: blueprint has errors: {val['errors']}")
    publish(db, org.id, v1, access_for(db, org.id, admin))
    clock.stamp(ago(28, 15), v1)

    # people refine it in the Studio (version 2), published by the admin
    b = v1
    acc_builder = access_for(db, org.id, builder)
    for who, section, op, key, rec in spec["edits"]:
        b = studio_edit(db, acc_builder if who == builder.email.split("@")[0] else access_for(db, org.id, people[who]), b, section, op, key, rec)
    clock.stamp(ago(21, 16), b)
    publish(db, org.id, b, access_for(db, org.id, admin))
    clock.stamp(ago(21, 17), b)
    for layer, values in spec.get("studio", {}).items():
        before = studio.get(org, layer)
        after = studio.save(org, layer, values)
        audit.record(db, org.id, builder.email, "studio.settings_changed", layer,
                     {"layer": studio.BY_ID[layer]["name"], "changes": {k: {"before": before.get(k), "after": after[k]} for k in values}}, commit=False)
    clock.stamp(ago(20, 10))
    live = b
    for who, section, op, key, rec in spec.get("draft_edits", []):  # a draft that is not live yet
        b = studio_edit(db, access_for(db, org.id, people[who]), b, section, op, key, rec)
    if b is not live:
        clock.stamp(ago(0.3, 9), b)

    # integrations: a server key for the product's backend and a publishable key for the chat widget
    for name, kind, role in (("Production backend", "secret", "Operator"), ("Website chat widget", "publishable", "Operator")):
        raw = new_token("ax_sk_" if kind == "secret" else "ax_pk_")
        k = ApiKey(org_id=org.id, name=name, kind=kind, prefix=raw[:12], key_hash=sha(raw), role_id=roles[role].id,
                   allowed_origins=[f"https://www.{spec['domain']}"] if kind == "publishable" else [], created_by=admin.id, last_used_at=ago(0.2, 8))
        db.add(k)
        db.flush()
        audit.record(db, org.id, admin.email, "api_key.created", k.prefix, {"name": name, "kind": kind}, commit=False)
        clock.stamp(ago(27, 9), k)
    db.commit()

    # weeks of work with the agent team
    pub = db.execute(select(Blueprint).where(Blueprint.org_id == org.id, Blueprint.status == "published")).scalar()
    for c in spec["conversations"]:
        run_conversation(db, org, conn, pub, people, c, clock)

    # Aria Watch: events the product sent, triaged by the watch rules; some became suggestions
    for e in sorted(spec["events"], key=lambda x: -x["days_ago"]):
        watch_event(db, org, pub, people, e, clock)

    rechain(db, org.id)
    return org


def publish(db, org_id, b: Blueprint, a: Access):
    for other in db.execute(select(Blueprint).where(Blueprint.org_id == org_id, Blueprint.status == "published")).scalars():
        other.status = "archived"
    b.status, b.published_by, b.published_at = "published", a.actor_id, NOW
    audit.record(db, org_id, a.actor_label, "blueprint.published", b.id, {"version": b.version}, commit=False)
    db.commit()


def studio_edit(db, a: Access, b: Blueprint, section, op, key, rec) -> Blueprint:
    content = copy.deepcopy(b.content)
    items = list(content.get(section) or [])
    if op == "add":
        items.append(rec)
    else:
        k = studio.SECTION_KEY.get(section)
        items = [rec if (x.get(k) if k else x) == key else x for x in items]
    content[section] = items
    nb = save_version(db, a, b, content)
    kind = {"add": "studio.record_added", "edit": "studio.record_edited"}[op]
    audit.record(db, a.org_id, a.actor_label, kind, nb.id, {"layer": studio.BY_ID[studio.layer_of(section)]["name"], "section": section,
                                                            "record": rec if isinstance(rec, str) else rec.get(studio.SECTION_KEY[section]),
                                                            "version": nb.version, "from_version": b.version}, commit=False)
    db.commit()
    return nb


def run_conversation(db, org, conn, pub, people, c, clock):
    u = people[c["by"]]
    a = access_for(db, org.id, u)
    when = ago(c["days_ago"], 9 + (len(c["q"]) % 7))
    cv = Conversation(org_id=org.id, user_id=u.id, title=c["q"][:80])
    db.add(cv)
    db.flush()
    lead = "executor" if c.get("plan") else "analyst"
    spec_agent = c.get("agent") or next((g["id"] for g in pub.content["agents"] if c.get("plan") and c["plan"]["steps"][0]["action"] in g.get("actions", [])),
                                       pub.content["agents"][0]["id"])
    spec_name = next(g["name"] for g in pub.content["agents"] if g["id"] == spec_agent)
    lead_name = {"executor": "Aria Executor", "analyst": "Aria Analyst"}[lead]
    trace = [{"type": "plan_start", "agent": "aria", "depth": 0, "text": f"Team: Aria Analyst, Aria Executor + {len(pub.content['agents'])} specialist(s)"},
             {"type": "delegate", "agent": "aria", "to": lead, "task": c["q"], "depth": 0},
             {"type": "agent_start", "agent": lead, "name": lead_name, "task": c["q"], "depth": 1},
             {"type": "delegate", "agent": lead, "to": spec_agent, "task": "Look up the facts for: " + c["q"], "depth": 1},
             {"type": "agent_start", "agent": spec_agent, "name": spec_name, "task": "Look up the facts", "depth": 2}]
    rows, cols = [], []
    if c.get("search"):
        hits = knowledge.search(db, org.id, c["search"], 3)
        trace.append({"type": "knowledge", "agent": spec_agent, "depth": 2, "query": c["search"],
                      "hits": [{"document": h["document"], "page": h["page"], "score": h["score"]} for h in hits]})
    if c.get("sql"):
        s = sqlite3.connect(upload_path(conn))
        s.row_factory = sqlite3.Row
        res = s.execute(c["sql"]).fetchall()
        s.close()
        cols = list(res[0].keys()) if res else []
        rows = [dict(r) for r in res]
        tables = [t for t in pub.content and [x["name"] for x in conn.schema_snapshot["tables"]] if f" {t}" in c["sql"]]
        trace.append({"type": "data", "agent": spec_agent, "depth": 2, "connection": conn.name, "sql": c["sql"] + " LIMIT 200", "tables": tables,
                      "rows": len(rows), "columns": cols, "preview": rows[:5]})
    trace.append({"type": "agent_end", "agent": spec_agent, "depth": 2, "report": f"Found {len(rows)} matching row(s)" if c.get("sql") else "Found the relevant policy passages"})
    plan = None
    if c.get("plan"):
        st = c["plan"]["steps"][0]
        ex = decisions.evaluate(pub.content, st["action"], st["facts"], pub.version)
        trace.append({"type": "rules", "agent": lead, "depth": 1, "action": st["action"], "verdict": ex["verdict"],
                      "hard": [{"id": h["id"], "status": h["status"]} for h in ex["hard"]], "gate": ex["gate"]})
        plan = plans.create(db, org.id, c["plan"]["title"], c["answer"], c["plan"]["steps"], source="console", conversation_id=cv.id, approver=a)
        trace.append({"type": "plan", "agent": lead, "depth": 1, "plan_id": plan.id, "title": plan.title, "steps": len(plan.steps), "approver": a.actor_label})
    trace.append({"type": "agent_end", "agent": lead, "depth": 1, "report": c["answer"][:300]})
    trace.append({"type": "final", "agent": "aria", "depth": 0, "seconds": round(6 + len(trace) * 1.7, 1)})
    answer = c["answer"].format(count=len(rows), table=md_table(cols, rows))
    m1 = Message(conversation_id=cv.id, role="user", content=c["q"])
    m2 = Message(conversation_id=cv.id, role="assistant", content=answer, trace=trace)
    db.add_all([m1, m2])
    clock.stamp(when, cv, m1, plan)
    m2.created_at = when + timedelta(seconds=25)
    db.commit()
    if not plan or not c.get("decide"):
        return
    plans.decide(db, a, plan, c["decide"] == "approve", "" if c["decide"] == "approve" else "Waiting for the warehouse grading first")
    made = db.execute(select(Decision).where(Decision.plan_id == plan.id)).scalars().all()
    clock.stamp(when + timedelta(minutes=4), plan, *made)
    if c.get("review"):
        who, ok, note, days = c["review"]
        d = next(x for x in made if x.status == "PENDING_REVIEW")
        decisions.review(db, access_for(db, org.id, people[who]), d, ok, note)
        db.commit()
        clock.stamp(ago(days, 15), d)


def watch_event(db, org, pub, people, e, clock):
    when = ago(e["days_ago"], 8 + (len(e["entity_id"]) % 9))
    ev = Event(org_id=org.id, type=e["type"], entity_id=e["entity_id"], data=e["data"], actor={"system": "product"}, occurred_at=when.isoformat())
    db.add(ev)
    db.flush()
    rule = next((r for r in pub.content.get("watch_rules") or [] if watch.rule_matches(r, ev)), None)
    sug = None
    if not rule:
        ev.status, ev.note = "ignored", "No watch rule matched, not investigated"
    elif not e.get("suggest"):
        ev.matched_rule, ev.status, ev.note = rule["id"], "no_action", "Investigated: nothing would clearly help, nobody was disturbed"
        ev.trace = [{"type": "agent_start", "agent": "watch", "name": "Aria Watch", "task": f"Investigate {ev.type} {ev.entity_id}", "depth": 1},
                    {"type": "agent_end", "agent": "watch", "report": "No change needed.", "depth": 1}]
    else:
        g = e["suggest"]
        owner = rule.get("owner_role") or "Reviewer"
        sug = Suggestion(org_id=org.id, event_id=ev.id, title=g["title"], rationale=g["rationale"], benefit=g["benefit"], owner_role=owner, steps=g["steps"])
        db.add(sug)
        db.flush()
        ev.matched_rule, ev.status, ev.suggestion_id, ev.note = rule["id"], "suggested", sug.id, f"Suggested to {owner}: {sug.title}"
        ev.trace = [{"type": "agent_start", "agent": "watch", "name": "Aria Watch", "task": f"Investigate {ev.type} {ev.entity_id}", "depth": 1},
                    {"type": "agent_end", "agent": "watch", "report": g["rationale"], "depth": 1}]
        audit.record(db, org.id, "Aria Watch", "suggestion.created", sug.id, {"event": ev.id, "rule": rule["id"], "owner_role": owner}, commit=False)
    clock.stamp(when, ev, *( [sug] if sug else []))
    if sug and e["suggest"].get("decide"):
        who, ok, days = e["suggest"]["decide"]
        watch.decide(db, access_for(db, org.id, people[who]), sug, ok, "Approved from Aria Watch")
        made = db.execute(select(Decision).where(Decision.plan_id == sug.plan_id)).scalars().all() if sug.plan_id else []
        p = db.get(Plan, sug.plan_id) if sug.plan_id else None
        clock.stamp(ago(days, 16), sug, *made, *([p] if p else []))


# ------------------------------------------------------------------ the onboarding login: a copy of Northwind as it is
def seed_onboarding(db):
    src = db.execute(select(Organisation).where(Organisation.name == NORTHWIND)).scalar()
    if not src:
        print("Northwind Rentals (demo) not found; skipping the onboarding login")
        return
    u = user(db, ONBOARDING, "Demo Onboarding")
    if db.execute(select(Membership).where(Membership.user_id == u.id)).scalar():
        return
    org, roles = create_org(db, "Northwind Rentals (onboarding demo)")
    org.product_description = src.product_description
    db.add(Membership(org_id=org.id, user_id=u.id, role_id=roles["Owner"].id))
    audit.record(db, org.id, u.email, "org.created", org.id, {"name": org.name}, commit=False)
    for d in db.execute(select(Document).where(Document.org_id == src.id)).scalars().all():
        text = "\n\n".join(c.text for c in db.execute(select(Chunk).where(Chunk.document_id == d.id).order_by(Chunk.ord)).scalars())
        data = text.encode()
        nd = Document(org_id=org.id, filename=d.filename, mime=d.mime, size=len(data), sha256=hashlib.sha256(data).hexdigest(), uploaded_by=u.id)
        db.add(nd)
        db.flush()
        p = DATA_DIR / "orgs" / org.id / "documents" / f"{nd.id}.bin"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(encrypt_bytes(data))
        knowledge.ingest(db, nd, data)
        audit.record(db, org.id, u.email, "knowledge.uploaded", nd.filename, {"status": nd.status, "chunks": nd.chunks}, commit=False)
    for b in db.execute(select(Blueprint).where(Blueprint.org_id == src.id)).scalars().all():
        db.add(Blueprint(org_id=org.id, version=b.version, status=b.status, content=b.content, validation=b.validation, progress=b.progress,
                         sources=b.sources, error=b.error, note=b.note, created_by=u.id))
    db.commit()


def reset(db):
    """Remove only the synthetic demo businesses and the onboarding copy, every row they own and their files."""
    import shutil
    from app.db import Base
    names = [s["name"] for s in BUSINESSES] + ["Northwind Rentals (onboarding demo)"]
    for org in db.execute(select(Organisation).where(Organisation.name.in_(names))).scalars().all():
        conv_ids = select(Conversation.id).where(Conversation.org_id == org.id)
        db.execute(Message.__table__.delete().where(Message.conversation_id.in_(conv_ids)))
        for t in reversed(Base.metadata.sorted_tables):
            if "org_id" in t.c and t.name != "organisations":
                db.execute(t.delete().where(t.c.org_id == org.id))
        db.execute(Organisation.__table__.delete().where(Organisation.id == org.id))
        shutil.rmtree(DATA_DIR / "orgs" / org.id, ignore_errors=True)
    db.commit()


PERSONAS = {
    "Peak Outdoor Gear (demo)": {"persona_name": "Sky", "persona_role": "outdoor gear expert and sales guide", "avatar": "teal",
                                 "traits": "enthusiastic, outdoorsy, practical, honest",
                                 "greeting": "Hi, I'm Sky. Planning a trip or sorting out an order? Tell me what you need and I'll find the right gear."},
    "Lumen Dental Clinics (demo)": {"persona_name": "Mia", "persona_role": "patient care coordinator", "avatar": "rose",
                                    "traits": "calm, reassuring, precise, kind",
                                    "greeting": "Hello, I'm Mia from Lumen Dental. I can help with appointments, deposits and anything about your visit."},
    "Brightline Freight (demo)": {"persona_name": "Max", "persona_role": "freight account manager", "avatar": "slate",
                                  "traits": "dependable, direct, numbers-first, courteous",
                                  "greeting": "Hi, I'm Max. Ask me about any shipment, delay or contract credit and I'll give you the facts."},
    "Northwind Rentals (demo)": {"persona_name": "Nora", "persona_role": "rental advisor", "avatar": "indigo",
                                 "traits": "friendly, helpful, clear, patient",
                                 "greeting": "Hi, I'm Nora from Northwind Rentals. Looking for equipment, or help with a booking?"},
}


PERSONAS.update(_VPERSONAS)


def seed_personas(db):
    """Each demo business speaks through its own persona, unless someone already set one in the Studio."""
    for name, p in PERSONAS.items():
        org = db.execute(select(Organisation).where(Organisation.name == name)).scalar()
        if not org or ((org.settings or {}).get("studio") or {}).get("interface", {}).get("persona_name") not in (None, "", "Aria"):
            continue
        studio.save(org, "interface", p)
    db.commit()


def seed_admin(db):
    """A super user who signs in as 'admin' and is Owner of every business, so one login reaches everything."""
    u = db.execute(select(User).where(User.username == ADMIN_USERNAME)).scalar()
    if not u:
        u = user(db, ADMIN_EMAIL, "Administrator")
        u.username = ADMIN_USERNAME
        db.flush()
    for org in db.execute(select(Organisation)).scalars().all():
        if db.execute(select(Membership).where(Membership.org_id == org.id, Membership.user_id == u.id)).scalar():
            continue
        owner = db.execute(select(Role).where(Role.org_id == org.id, Role.name == "Owner")).scalar()
        if not owner:
            continue
        db.add(Membership(org_id=org.id, user_id=u.id, role_id=owner.id))
        audit.record(db, org.id, "Demo setup", "user.joined", u.id, {"user": ADMIN_EMAIL, "role": "Owner", "note": "super user"}, commit=False)
    db.commit()


def main():
    init_db()
    db = SessionLocal()
    try:
        if "--reset" in sys.argv:
            reset(db)
        owner = db.execute(select(User).where(User.email == DEMO_OWNER)).scalar()
        if not owner:  # a fresh install: create the demo owner and their first business, mid-setup, as if they had signed up
            owner = user(db, DEMO_OWNER, "Demo Owner")
            org, roles = create_org(db, NORTHWIND)
            org.product_description = ("Northwind Rentals hires out construction and event equipment to businesses from four depots. "
                                       "Customers book online; depot staff handle returns, damage and late fees.")
            db.add(Membership(org_id=org.id, user_id=owner.id, role_id=roles["Owner"].id))
            audit.record(db, org.id, DEMO_OWNER, "org.created", org.id, {"name": org.name}, commit=False)
            db.commit()
            print(f"created  {NORTHWIND} for {DEMO_OWNER}")
        for spec in BUSINESSES:
            if existing := db.execute(select(Organisation).where(Organisation.name == spec["name"])).scalar():
                if (existing.settings or {}).get("model_group") != MODEL_GROUP:
                    existing.settings = {**(existing.settings or {}), "model_group": MODEL_GROUP}
                    db.commit()
                print(f"exists   {spec['name']}")
                continue
            org = seed_business(db, spec, owner)
            print(f"created  {spec['name']}  audit chain: {audit.verify(db, org.id)}")
        seed_onboarding(db)
        print("onboarding login:", ONBOARDING)
        seed_personas(db)
        seed_admin(db)
        print("super user login:", ADMIN_USERNAME)
    finally:
        db.close()


if __name__ == "__main__":
    os.environ.setdefault("ARIAX_ENV", "development")
    main()
