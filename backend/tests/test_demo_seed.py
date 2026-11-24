"""The demo businesses stay valid as the product evolves: blueprints pass the symbolic check, the audit chain verifies,
and the history contains every kind of outcome."""
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import seed_demo  # noqa: E402
from app import audit  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Blueprint, Decision, Event, Suggestion  # noqa: E402


def test_demo_businesses_are_valid_and_complete():
    db = SessionLocal()
    try:
        owner = seed_demo.user(db, "seed.owner@example.com", "Seed Owner")
        for spec in seed_demo.BUSINESSES:
            org = seed_demo.seed_business(db, {**spec, "name": spec["name"] + " test", "domain": "t-" + spec["domain"]}, owner)
            assert audit.verify(db, org.id)["ok"], spec["name"]
            live = db.execute(select(Blueprint).where(Blueprint.org_id == org.id, Blueprint.status == "published")).scalar()
            assert live.version >= 2 and live.validation["ok"] and live.provenance, spec["name"]
            statuses = {d.status for d in db.execute(select(Decision).where(Decision.org_id == org.id)).scalars()}
            assert {"EXECUTED", "BLOCKED"} <= statuses, (spec["name"], statuses)
            ev = {e.status for e in db.execute(select(Event).where(Event.org_id == org.id)).scalars()}
            assert {"ignored", "suggested"} <= ev, (spec["name"], ev)
            assert db.execute(select(Suggestion).where(Suggestion.org_id == org.id, Suggestion.status == "pending")).scalar()
    finally:
        db.close()
