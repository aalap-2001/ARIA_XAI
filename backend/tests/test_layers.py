"""Studio layer views: each layer reports what it is doing, the persona speaks for the business, Aria Watch learns from
owners' feedback, and people can sign in with a username."""
from conftest import PW, Client
from test_product import member, setup_product

from app import watch
from app.db import SessionLocal
from app.models import Event, Suggestion, User


def test_every_layer_reports_live_data_and_only_rule_layers_are_editable(signup):
    cl = signup()
    setup_product(cl)
    st = {x["id"]: x for x in cl.get("/api/studio").json()["layers"]}
    assert st["knowledge"]["readonly"] is True and st["knowledge"]["can_edit_records"] is False
    assert st["cognitive"]["can_edit_records"] is True
    for layer in ("cognitive", "motivation", "knowledge", "swarm", "interface", "governance"):
        r = cl.get(f"/api/studio/{layer}/live")
        assert r.status_code == 200, (layer, r.text)
    mem = cl.get("/api/studio/knowledge/live").json()
    assert {s["id"] for s in mem["stores"]} == {"documents", "data", "blueprint", "conversations", "decisions", "events"}
    assert any(t["store"] == "Documents" for t in mem["timeline"])
    gov = cl.get("/api/studio/governance/live").json()
    assert gov["audit"]["verify"]["ok"] is True
    assert cl.get("/api/studio/nope/live").status_code == 404


def test_persona_is_set_in_the_studio_used_in_chat_and_audited(signup):
    cl = signup("Trail Shop")
    setup_product(cl)
    p = cl.get("/api/team").json()["persona"]
    assert p["name"] == "Aria" and p["role"] == "Trail Shop sales and service guide" and "Aria" in p["greeting"]
    r = cl.put("/api/studio/interface/settings", json={"settings": {"persona_name": "Sky", "persona_role": "gear expert", "traits": "calm, expert"}})
    assert r.status_code == 200, r.text
    p = cl.get("/api/team").json()["persona"]
    assert (p["name"], p["role"], p["traits"]) == ("Sky", "gear expert", ["calm", "expert"]) and p["greeting"].startswith("Hi, I'm Sky")
    assert cl.put("/api/studio/interface/settings", json={"settings": {"persona_name": "x" * 41}}).status_code == 400
    assert "studio.settings_changed" in [e["kind"] for e in cl.get("/api/audit").json()]
    # an Operator cannot change it
    op = member(cl, "op.persona@example.com", "Operator")
    assert op.put("/api/studio/interface/settings", json={"settings": {"persona_name": "Bob"}}).status_code == 403


def test_aria_watch_learns_from_owner_decisions(signup):
    cl = signup()
    setup_product(cl)
    org_id = cl.get("/api/auth/me").json()["org"]["id"]
    db = SessionLocal()
    try:
        ev = Event(org_id=org_id, type="stock.changed", status="suggested", matched_rule="low_stock")
        db.add(ev)
        db.flush()
        db.add(Suggestion(org_id=org_id, event_id=ev.id, title="Order 500 tents", status="rejected", decided_by="Dana",
                          note="Too many, we only sell 40 a month"))
        db.commit()
        learned = watch.lessons(db, org_id, "low_stock")
        assert learned == ['Dana rejected "Order 500 tents". Their note: Too many, we only sell 40 a month']
        assert watch.lessons(db, org_id, "other_rule") == []
    finally:
        db.close()


def test_sign_in_with_username_or_email(signup):
    cl = signup()
    db = SessionLocal()
    try:
        db.query(User).filter(User.email == cl.email).one().username = "boss"
        db.commit()
    finally:
        db.close()
    for ident in ("boss", "BOSS", cl.email):
        c = Client()
        assert c.post("/api/auth/login", json={"email": ident, "password": PW}).status_code == 200, ident
    bad = Client().post("/api/auth/login", json={"email": "boss", "password": "wrong-password"})
    assert bad.status_code == 401 and "username" in bad.json()["detail"]


def test_platform_model_comes_from_the_server_environment(signup, monkeypatch):
    from app.llm.service import platform_connector, resolve
    cl = signup("No Model Co")
    org_id = cl.get("/api/auth/me").json()["org"]["id"]
    db = SessionLocal()
    try:
        monkeypatch.delenv("ARIAX_LLM_API_KEY", raising=False)
        assert resolve(db, org_id) == (None, None)
        monkeypatch.setenv("ARIAX_LLM_API_KEY", "sk-test-not-real")
        monkeypatch.setenv("ARIAX_LLM_MODEL", "claude-opus-5-5")
        c, shared = resolve(db, org_id)
        assert c.id == "platform" and c.model == "claude-opus-5-5" and c.provider == "anthropic" and shared is None
        assert "sk-test-not-real" not in (c.secret_enc or "")
        assert platform_connector() is not None
    finally:
        db.close()
    # the roles screen no longer offers AI model permissions
    cat = cl.get("/api/roles/catalog")
    assert cat.status_code == 200 and "llm" not in [r["id"] for r in cat.json()["resources"]]
