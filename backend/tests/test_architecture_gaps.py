"""Gaps closed against the updated HLD: kill switch, egress watchdog, four-part explanation, noisy-OR."""
import json
import sqlite3
import threading
from http.server import HTTPServer

from test_product import Hook, chat, plan_from, setup_product

from ariax.rules.engine import RuleEngine


def with_webhook(cl, bp):
    srv = HTTPServer(("127.0.0.1", 0), Hook)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    content = bp["content"]
    content["actions"][0]["executor"] = {"type": "webhook", "url": f"http://127.0.0.1:{srv.server_port}/hook"}
    nb = cl.put(f"/api/blueprints/{bp['id']}", json={"content": content}).json()
    cl.post(f"/api/blueprints/{nb['id']}/publish")
    return srv


def test_kill_switch_halts_risky_actions_and_is_audited(signup):
    cl = signup()
    srv = with_webhook(cl, setup_product(cl))
    n = len(Hook.got)
    assert cl.post("/api/org/kill-switch", json={"active": True, "reason": "suspected incident"}).json()["active"]
    assert cl.get("/api/auth/me").json()["org"]["kill_switch"]["reason"] == "suspected incident"
    res = cl.post(f"/api/plans/{plan_from(chat(cl, 'Refund order 1001'))}/decide", json={"approve": True}).json()["results"][0]
    assert res["effect"] == "BLOCK" and "Kill switch" in res["reasons"][0] and len(Hook.got) == n
    # LOW risk actions are not halted
    low = cl.post(f"/api/plans/{plan_from(chat(cl, 'Mark order 1002 as refunded'))}/decide", json={"approve": True}).json()["results"][0]
    assert low["effect"] == "ALLOW"
    cl.post("/api/org/kill-switch", json={"active": False})
    ok = cl.post(f"/api/plans/{plan_from(chat(cl, 'Refund order 1001'))}/decide", json={"approve": True}).json()["results"][0]
    assert ok["status"] == "EXECUTED" and len(Hook.got) == n + 1
    kinds = [e["kind"] for e in cl.get("/api/audit").json()]
    assert "kill_switch.activated" in kinds and "kill_switch.released" in kinds
    srv.shutdown()


def test_watchdog_reconciles_sends_with_approved_decisions(signup):
    cl = signup()
    srv = with_webhook(cl, setup_product(cl))
    cl.post(f"/api/plans/{plan_from(chat(cl, 'Refund order 1001'))}/decide", json={"approve": True})
    wd = cl.get("/api/audit/watchdog").json()
    assert wd["ok"] and wd["checked"] == 1
    from app.config import DATA_DIR
    db = sqlite3.connect(str(DATA_DIR / "test.db"))
    org = cl.get("/api/auth/me").json()["org"]["id"]
    db.execute("INSERT INTO egress_log (org_id, decision_id, executor, target, payload_hash, at) VALUES (?, NULL, 'webhook', 'http://x', 'h', '2026-01-01')", (org,))
    db.commit()
    bad = cl.get("/api/audit/watchdog").json()
    assert not bad["ok"] and bad["incidents"][0]["issue"] == "sent without a decision"
    srv.shutdown()


def test_explanation_has_four_parts_with_extraction_trace(signup):
    cl = signup()
    setup_product(cl)
    pid = plan_from(chat(cl, "Refund order 1001"))
    res = cl.post(f"/api/plans/{pid}/decide", json={"approve": True}).json()["results"][0]
    ex = cl.get(f"/api/decisions/{res['decision_id']}").json()["explanation"]
    assert {"extraction", "soft", "gate", "hard"} <= set(ex)
    assert {e["fact"] for e in ex["extraction"]} == {"refund_amount", "days_since_order", "damage_score"}


def test_noisy_or_and_extraction_confidence_in_the_engine():
    rules = {"features": {"a": {"from": "facts.a", "type": "bool", "confidence_from": "evidence.a.confidence"},
                          "b": {"from": "facts.b", "type": "bool"}},
             "soft": [{"id": "s", "output": "s", "combine": "noisy_or", "inputs": [{"feature": "a", "weight": 0.6}, {"feature": "b", "weight": 0.5}]}],
             "thresholds": [{"signal": "s", "from": "s", "assert_above": 0.75, "deny_below": 0.2}], "hard": []}
    ex = RuleEngine().evaluate(rules, {"facts": {"a": True, "b": True}, "evidence": {"a": {"confidence": 0.9}}}, "t")
    assert ex["soft"]["s"]["score"] == 0.8 and ex["gate"][0]["outcome"] == "TRUE"   # 1 - 0.4 * 0.5
    assert ex["features"]["a"]["extraction_confidence"] == 0.9
    assert json.dumps(ex)  # serialisable for the explanation bundle
