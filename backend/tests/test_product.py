"""End-to-end product tests: accounts, roles, tenancy, LLM connectors, understanding, agents, governance."""
import hashlib
import hmac
import json
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from conftest import PW, Client

from app.sql_guard import GuardError, guard

ORDERS = ("order_id,customer,amount,days,damage,status\n1001,Ana,300,10,0.1,open\n1002,Ben,900,12,0.0,open\n"
          "1003,Cy,200,45,0.0,open\n1004,Di,150,5,0.95,open\n")
POLICY = b"# Refund policy\nRefunds are allowed within 30 days of the order. Damaged items are not refunded. Refunds of 500 or more need a manager."


def setup_product(cl):
    """Mock model + one CSV connection + one document + description → published blueprint."""
    r = cl.post("/api/llm/connectors", json={"name": "Mock", "provider": "mock", "values": {"api_key": "good-key-123456"}, "model": "mock-large"})
    assert r.status_code == 200, r.text
    r = cl.post("/api/data/upload", data={"name": "Orders"}, files={"file": ("orders.csv", ORDERS, "text/csv")})
    assert r.status_code == 200 and r.json()["status"] == "ready", r.text
    r = cl.post("/api/knowledge/upload", files=[("files", ("policy.md", POLICY, "text/markdown"))])
    assert r.json()[0]["status"] == "ready", r.text
    cl.put("/api/product", json={"description": "We rent equipment and handle refunds."})
    bp = cl.post("/api/blueprints/generate").json()
    for _ in range(100):
        bp = cl.get(f"/api/blueprints/{bp['id']}").json()
        if bp["status"] != "generating":
            break
        time.sleep(0.05)
    assert bp["status"] == "draft", bp
    assert bp["validation"]["ok"], bp["validation"]
    assert bp["content"]["industry"] == "Equipment rental"  # inferred, never selected
    r = cl.post(f"/api/blueprints/{bp['id']}/publish")
    assert r.status_code == 200, r.text
    return bp


def chat(cl, text):
    cv = cl.post("/api/conversations").json()["id"]
    r = cl.post(f"/api/conversations/{cv}/messages", json={"message": text})
    events = [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]
    return events


# ------------------------------------------------------------------ accounts & sessions
def test_signup_login_logout_and_csrf(signup):
    cl = signup()
    me = cl.get("/api/auth/me").json()
    assert me["role"] == "Owner" and me["org"]["name"] == "Acme Rentals"
    bad = Client()
    assert bad.post("/api/auth/login", json={"email": cl.email, "password": "wrong-Password1"}).status_code == 401
    # writes without the CSRF header are refused even with a valid session cookie
    assert cl.c.patch("/api/org", json={"name": "X"}).status_code == 403
    assert cl.patch("/api/org", json={"name": "Acme Rentals Ltd"}).status_code == 200
    cl.post("/api/auth/logout")
    assert cl.c.get("/api/auth/me").status_code == 401


def test_weak_password_and_rate_limit(signup):
    c = Client()
    assert c.post("/api/auth/signup", json={"org_name": "Weak Org", "name": "W", "email": "weak@example.com", "password": "short1A"}).status_code == 400
    cl = signup()
    other = Client()
    codes = [other.post("/api/auth/login", json={"email": cl.email, "password": "Nope-Nope-1"}).status_code for _ in range(11)]
    assert codes[-1] == 429


# ------------------------------------------------------------------ LLM connectors
def test_llm_connector_flow_and_secrets_never_leak(signup):
    cl = signup()
    secret = "sk-mock-SUPERSECRET-9876"
    assert cl.post("/api/llm/models", json={"provider": "mock", "values": {"api_key": "bad-key"}}).json()["ok"] is False
    models = cl.post("/api/llm/models", json={"provider": "mock", "values": {"api_key": secret}}).json()
    assert models["ok"] and "mock-large" in models["models"]
    fail = cl.post("/api/llm/test", json={"provider": "mock", "values": {"api_key": "bad-key"}, "model": "mock-large"}).json()
    assert fail["ok"] is False and "401" in fail["error"]
    ok = cl.post("/api/llm/test", json={"provider": "mock", "values": {"api_key": secret}, "model": "mock-large"}).json()
    assert ok["ok"] is True and ok["latency_ms"] >= 0
    saved = cl.post("/api/llm/connectors", json={"name": "Primary", "provider": "mock", "values": {"api_key": secret},
                                                 "model": "mock-large", "test_result": ok}).json()
    assert saved["is_default"] and saved["status"] == "ok" and saved["secret_hint"] == "••••9876"
    listing = cl.get("/api/llm/connectors").text
    assert secret not in listing
    from app.config import DATA_DIR
    raw = sqlite3.connect(str(DATA_DIR / "test.db")).execute("SELECT secret_enc FROM llm_connectors").fetchall()
    assert all(secret not in (r[0] or "") for r in raw)  # encrypted at rest
    # testing a saved connector with blank key reuses the stored (encrypted) secret
    again = cl.post("/api/llm/test", json={"provider": "mock", "values": {}, "connector_id": saved["id"], "model": "mock-large"}).json()
    assert again["ok"]
    cat = cl.get("/api/llm/catalog").json()
    assert [g["id"] for g in cat["groups"]] == ["saas", "enterprise", "local"]


# ------------------------------------------------------------------ roles & access
def test_invite_roles_and_custom_scopes(signup):
    owner = signup()
    setup_product(owner)
    roles = {r["name"]: r for r in owner.get("/api/roles").json()}
    assert set(roles) >= {"Owner", "Org admin", "Builder", "Reviewer", "Operator"}
    inv = owner.post("/api/users/invite", json={"email": "op@example.com", "role_id": roles["Operator"]["id"]}).json()
    token = inv["invite_url"].rsplit("/", 1)[1]
    op = Client()
    assert op.post(f"/api/invites/{token}/accept", json={"name": "Op", "password": PW}).status_code == 200
    op.refresh()
    assert op.get("/api/llm/connectors").status_code == 403
    assert op.get("/api/users").status_code == 403
    assert op.get("/api/team").json()["agents"]  # operators can use the team
    # a custom role that may use the team but no agents and no tables
    cat = owner.get("/api/roles/catalog").json()
    assert cat["agents"][0]["id"] == "support_analyst" and cat["data"][0]["tables"] == ["orders"]
    r = owner.post("/api/roles", json={"name": "Restricted", "permissions": ["chat:use"], "scopes": {"agents": [], "data": {}, "actions": []}})
    assert r.status_code == 200, r.text
    m = next(x for x in owner.get("/api/users").json()["members"] if x["email"] == "op@example.com")
    owner.patch(f"/api/users/{m['id']}", json={"role_id": r.json()["id"]})
    assert op.get("/api/team").json()["agents"] == []
    # nobody can remove the last owner
    me = next(x for x in owner.get("/api/users").json()["members"] if x["you"])
    assert owner.patch(f"/api/users/{me['id']}", json={"status": "deactivated"}).status_code == 400


def test_tenant_isolation(signup):
    a, b = signup("Org A"), signup("Org B")
    bp = setup_product(a)
    conn = a.get("/api/llm/connectors").json()[0]
    data = a.get("/api/data/connections").json()[0]
    assert b.get(f"/api/blueprints/{bp['id']}").status_code == 404
    assert b.patch(f"/api/llm/connectors/{conn['id']}", json={"name": "pwn"}).status_code == 404
    assert b.get(f"/api/data/connections/{data['id']}/tables/orders").status_code == 404
    assert b.get("/api/llm/connectors").json() == []
    assert b.get("/api/knowledge/search?q=refund").json() == []


# ------------------------------------------------------------------ the symbolic SQL guard
@pytest.mark.parametrize("sql,why", [
    ("DELETE FROM orders", "SELECT"), ("SELECT 1; DROP TABLE orders", "one SQL"), ("SELECT * FROM secrets", "does not exist"),
    ("SELECT * FROM payroll", "not allowed"), ("SELECT pg_sleep(10) FROM orders", "pg_sleep"),
    ("WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x", "not allowed"),
])
def test_sql_guard_refuses(sql, why):
    with pytest.raises(GuardError, match=why):
        guard(sql, "postgres", ["orders", "payroll"], ["orders"])


def test_sql_guard_limits_and_allows():
    safe, used = guard("SELECT * FROM orders", "sqlite", ["orders"], ["*"])
    assert "LIMIT 200" in safe and used == ["orders"]
    safe, _ = guard("SELECT a FROM orders UNION SELECT a FROM orders", "postgres", ["orders"], ["orders"])
    assert safe.upper().endswith("LIMIT 200")


# ------------------------------------------------------------------ understanding → agents → neuro-symbolic decisions
class Hook(BaseHTTPRequestHandler):
    got = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        Hook.got.append((body, self.headers.get("X-AriaX-Signature")))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


def plan_from(events):
    p = next((e for e in events if e.get("type") == "plan"), None)
    assert p, [e.get("type") for e in events]
    return p["plan_id"]


def member(owner, email, role_name, limit="keep"):
    roles = {r["name"]: r for r in owner.get("/api/roles").json()}
    r = roles[role_name]
    if limit != "keep":
        owner.patch(f"/api/roles/{r['id']}", json={"name": r["name"], "permissions": r["permissions"], "scopes": {**r["scopes"], "approval_limit": limit}})
    tok = owner.post("/api/users/invite", json={"email": email, "role_id": r["id"]}).json()["invite_url"].rsplit("/", 1)[1]
    m = Client()
    m.post(f"/api/invites/{tok}/accept", json={"name": role_name, "password": PW})
    m.refresh()
    return m


def test_executor_plans_need_the_users_approval_and_record_accountability(signup):
    cl = signup()
    bp = setup_product(cl)
    srv = HTTPServer(("127.0.0.1", 0), Hook)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    content = bp["content"]
    content["actions"][0]["executor"] = {"type": "webhook", "url": f"http://127.0.0.1:{srv.server_port}/hook"}
    nb = cl.put(f"/api/blueprints/{bp['id']}", json={"content": content}).json()  # editing published → new draft
    assert cl.post(f"/api/blueprints/{nb['id']}/publish").status_code == 200

    n = len(Hook.got)
    ev = chat(cl, "Refund order 1001")  # orchestrator → Aria Executor → plan; NOTHING runs yet
    assert {"delegate", "agent_start", "data", "plan", "final"} <= {e.get("type") for e in ev}
    pid = plan_from(ev)
    plan = cl.get(f"/api/plans/{pid}").json()
    assert plan["status"] == "awaiting_approval" and plan["can_decide"] and len(Hook.got) == n
    step = plan["steps"][0]
    assert step["verdict"] == "VALID" and step["authority"]["within"]  # Owner: unlimited, may approve HIGH risk

    done = cl.post(f"/api/plans/{pid}/decide", json={"approve": True, "note": "go"}).json()
    res = done["results"][0]
    assert done["status"] == "executed" and done["accountable"] == cl.email and res["effect"] == "ALLOW"
    body, sig = Hook.got[-1]
    secret = cl.get("/api/webhook-secret?reveal=true").json()["secret"]
    assert sig == "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert json.loads(body)["accountable"] == cl.email and json.loads(body)["decision_id"] == res["decision_id"]
    assert cl.post(f"/api/plans/{pid}/decide", json={"approve": True}).status_code == 409  # single use

    # rules still decide: 45 days old → blocked even though the owner approved
    blocked = cl.post(f"/api/plans/{plan_from(chat(cl, 'Refund order 1003'))}/decide", json={"approve": True}).json()
    assert blocked["results"][0]["effect"] == "BLOCK" and blocked["status"] == "blocked"
    # rejecting changes nothing
    m = len(Hook.got)
    rej = cl.post(f"/api/plans/{plan_from(chat(cl, 'Refund order 1001'))}/decide", json={"approve": False}).json()
    assert rej["status"] == "rejected" and len(Hook.got) == m
    audit_kinds = [e["kind"] for e in cl.get("/api/audit").json()]
    assert {"plan.proposed", "plan.approved", "plan.rejected", "decision.executed"} <= set(audit_kinds)
    srv.shutdown()


def test_risk_is_judged_against_the_approving_user_and_escalates_to_the_owner_role(signup):
    owner = signup()
    setup_product(owner)
    op = member(owner, "op@example.com", "Operator")               # approval limit 0, no approval authority
    rev = member(owner, "rev@example.com", "Reviewer", limit=500)   # owns the refund area, up to 500
    pid = plan_from(chat(op, "Refund order 1001"))
    assert owner.post(f"/api/plans/{pid}/decide", json={"approve": True}).status_code == 403  # only the person it was proposed to
    step = op.get(f"/api/plans/{pid}").json()["steps"][0]
    assert step["authority"]["within"] is False
    res = op.post(f"/api/plans/{pid}/decide", json={"approve": True}).json()["results"][0]
    assert (res["effect"], res["status"]) == ("REVIEW", "PENDING_REVIEW")  # beyond the operator's authority → Reviewer
    mine = rev.get("/api/decisions?status=PENDING_REVIEW&mine=true").json()
    assert [d["id"] for d in mine] == [res["decision_id"]]
    r = rev.post(f"/api/decisions/{res['decision_id']}/review", json={"approve": True, "note": "fine"}).json()
    assert r["status"] == "EXECUTED" and r["accountable"] == "rev@example.com"


def test_database_write_actions_are_declared_enabled_and_single_row(signup):
    cl = signup()
    setup_product(cl)
    conn = cl.get("/api/data/connections").json()[0]
    first = cl.post(f"/api/plans/{plan_from(chat(cl, 'Mark order 1002 as refunded'))}/decide", json={"approve": True}).json()
    assert first["results"][0]["status"] == "FAILED" and "not enabled" in first["results"][0]["execution"]["error"]
    assert cl.patch(f"/api/data/connections/{conn['id']}", json={"allow_writes": True}).json()["allow_writes"] is True
    ok = cl.post(f"/api/plans/{plan_from(chat(cl, 'Mark order 1002 as refunded'))}/decide", json={"approve": True}).json()
    assert ok["results"][0]["status"] == "EXECUTED", ok
    rows = cl.get(f"/api/data/connections/{conn['id']}/tables/orders").json()["rows"]
    assert {r[0]: r[5] for r in rows} == {1001: "open", 1002: "refunded", 1003: "open", 1004: "open"}  # only that row, only that column


def wait_event(cl, eid, timeout=10):
    for _ in range(timeout * 20):
        e = next((x for x in cl.get("/api/events").json() if x["id"] == eid), None)
        if e and e["status"] not in ("received", "investigating"):
            return e
        time.sleep(0.05)
    raise AssertionError("event not processed")


def test_aria_watch_ignores_routine_events_and_suggests_to_the_owner(signup):
    owner = signup()
    setup_product(owner)
    roles = {r["name"]: r for r in owner.get("/api/roles").json()}
    sk = owner.post("/api/api-keys", json={"name": "Product", "kind": "secret", "role_id": roles["Operator"]["id"]}).json()["key"]
    send = lambda body: owner.c.post("/v1/events", headers={"Authorization": f"Bearer {sk}"}, json=body)  # noqa: E731
    small = send({"type": "refund.requested", "entity_id": "1001", "data": {"order_id": 1001, "amount": 300}}).json()
    other = send({"type": "order.viewed", "entity_id": "1002", "data": {"order_id": 1002}}).json()
    big = send({"type": "refund.requested", "entity_id": "1002", "data": {"order_id": 1002, "amount": 900}}).json()
    assert wait_event(owner, small["id"])["status"] == "ignored"   # symbolic triage: no model call
    assert wait_event(owner, other["id"])["status"] == "ignored"
    e = wait_event(owner, big["id"])
    assert e["status"] == "suggested" and e["matched_rule"] == "large_refund_request"
    sug = owner.get("/api/suggestions?status=pending").json()[0]
    assert sug["owner_role"] == "Reviewer" and sug["steps"][0]["action"] == "ISSUE_REFUND"
    op = member(owner, "op2@example.com", "Operator")
    assert op.post(f"/api/suggestions/{sug['id']}/decide", json={"approve": True}).status_code == 403  # not the owner role
    done = owner.post(f"/api/suggestions/{sug['id']}/decide", json={"approve": True}).json()
    assert done["status"] == "executed" and done["plan"]["accountable"] == owner.email and done["plan"]["source"] == "watch"


def test_hard_engine_refuses_ungated_input():
    from ariax.core.errors import GateViolation
    from ariax.rules.engine import HardEngine
    with pytest.raises(GateViolation):
        HardEngine().validate([], {}, {"damage_risk": False})


def test_blueprint_validation_catches_bad_references(signup):
    from app.blueprint import normalise, validate
    c = normalise({"summary": "x", "facts": [{"name": "a", "type": "string", "description": ""}],
                   "signals": [{"id": "s", "description": "", "inputs": [{"fact": "a", "weight": 1}], "assert_above": 0.2, "deny_below": 0.8}],
                   "rules": [{"id": "r", "description": "", "applies_to": ["NOPE"], "condition": {"path": "ghost", "op": "<", "value": 1}}],
                   "actions": [], "agents": [{"id": "g", "name": "G", "purpose": "", "instructions": "", "tools": ["query_data"],
                                              "data_scope": [{"connection_id": "dc_x", "tables": ["t"]}]}]})
    errs = " | ".join(validate(c, {})["errors"])
    for needle in ["text; soft signals", "deny_below ≤ assert_above", "fact 'ghost'", "unknown action 'NOPE'", "connection 'dc_x'"]:
        assert needle in errs


# ------------------------------------------------------------------ public API, widget, audit
def test_public_api_and_widget_origin(signup):
    cl = signup()
    setup_product(cl)
    roles = {r["name"]: r for r in cl.get("/api/roles").json()}
    assert cl.post("/api/api-keys", json={"name": "x", "kind": "secret", "role_id": roles["Owner"]["id"]}).status_code == 400
    sk = cl.post("/api/api-keys", json={"name": "Backend", "kind": "secret", "role_id": roles["Operator"]["id"]}).json()["key"]
    r = cl.c.post("/v1/agents/chat", headers={"Authorization": f"Bearer {sk}"}, json={"message": "Refund order 1001", "end_user_id": "u1"})
    assert r.status_code == 200 and r.json()["reply"] and r.json()["plans"]  # no human in the loop → plan waits for the owner role
    assert cl.c.post("/v1/agents/chat", headers={"Authorization": "Bearer ax_sk_wrong"}, json={"message": "hi"}).status_code == 401
    pk = cl.post("/api/api-keys", json={"name": "Site", "kind": "publishable", "role_id": roles["Operator"]["id"],
                                        "allowed_origins": ["https://shop.example.com"]}).json()["key"]
    bad = cl.c.post("/v1/widget/chat", headers={"X-AriaX-Key": pk, "Origin": "https://evil.example"}, json={"message": "hi"})
    assert bad.status_code == 403
    good = cl.c.post("/v1/widget/chat", headers={"X-AriaX-Key": pk, "Origin": "https://shop.example.com"}, json={"message": "Refund order 1001"})
    assert good.status_code == 200 and good.headers["access-control-allow-origin"] == "https://shop.example.com"
    assert "data-key" in cl.c.get("/widget.js").text or "X-AriaX-Key" in cl.c.get("/widget.js").text


def test_audit_chain_is_tamper_evident(signup):
    cl = signup()
    cl.patch("/api/org", json={"name": "Renamed"})
    assert cl.get("/api/audit/verify").json()["ok"]
    from app.config import DATA_DIR
    db = sqlite3.connect(str(DATA_DIR / "test.db"))
    db.execute("UPDATE audit SET actor='someone-else' WHERE kind='org.updated'")
    db.commit()
    assert cl.get("/api/audit/verify").json()["ok"] is False
