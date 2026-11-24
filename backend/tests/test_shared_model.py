"""Businesses in a model-sharing group (set server-side only) run on one connector; everyone else never can."""
from test_product import chat

from app.db import SessionLocal
from app.models import Organisation, UsageEvent


def _group(cl, group):
    db = SessionLocal()
    try:
        o = db.get(Organisation, cl.get("/api/auth/me").json()["org"]["id"])
        o.settings = {**(o.settings or {}), "model_group": group}
        db.commit()
        return o.id
    finally:
        db.close()


def test_group_members_share_one_model_and_others_cannot(signup):
    a, b, outsider = signup("Group Member A"), signup("Group Member B"), signup("Outsider Co")
    a_id, b_id = _group(a, "g1"), _group(b, "g1")
    assert b.get("/api/setup").json()["ai_model"] is False
    assert b.get("/api/llm/shared").json() == {"group": "g1", "source": None}

    r = a.post("/api/llm/connectors", json={"name": "Mock", "provider": "mock", "values": {"api_key": "good-key-123456"}, "model": "mock-large"})
    assert r.status_code == 200, r.text

    # B now runs on A's model: checklist done, source shown, but no secret and no connector of its own
    assert b.get("/api/setup").json()["ai_model"] is True
    src = b.get("/api/llm/shared").json()["source"]
    assert src["business"] == "Group Member A" and src["model"] == "mock-large" and "secret" not in str(src).lower()
    assert b.get("/api/llm/connectors").json() == []

    # a call made in B is metered to B
    chat(b, "What is our refund policy?")
    db = SessionLocal()
    try:
        assert db.query(UsageEvent).filter(UsageEvent.org_id == b_id).count() >= 1
    finally:
        db.close()

    # a business outside the group gets nothing, and cannot join a group through the API
    assert outsider.get("/api/setup").json()["ai_model"] is False
    outsider.patch("/api/org", json={"settings": {"model_group": "g1"}})
    assert outsider.get("/api/llm/shared").json()["group"] is None
