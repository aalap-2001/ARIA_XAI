import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="ariax-test-")
os.environ["ARIAX_DATA_DIR"] = _TMP
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP, 'test.db').as_posix()}"
os.environ["ARIAX_ENABLE_MOCK_LLM"] = "1"
os.environ["ARIAX_BLOCK_PRIVATE_NETWORKS"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.llm.base import ChatResult, ToolCall  # noqa: E402
from app.llm.providers import MockProvider  # noqa: E402
from app.main import app  # noqa: E402

PW = "Str0ngPassword!"


class Client:
    """TestClient wrapper that carries the CSRF token like the browser app does."""

    def __init__(self):
        self.c = TestClient(app)
        self.c.__enter__()
        self.csrf = None

    def _h(self):
        return {"x-csrf-token": self.csrf} if self.csrf else {}

    def refresh(self):
        r = self.c.get("/api/auth/me")
        if r.status_code == 200:
            self.csrf = r.json()["csrf"]
        return r

    def get(self, url, **kw):
        return self.c.get(url, headers=self._h(), **kw)

    def post(self, url, **kw):
        h = {**self._h(), **kw.pop("headers", {})}
        return self.c.post(url, headers=h, **kw)

    def put(self, url, **kw):
        return self.c.put(url, headers=self._h(), **kw)

    def patch(self, url, **kw):
        return self.c.patch(url, headers=self._h(), **kw)

    def delete(self, url, **kw):
        return self.c.delete(url, headers=self._h(), **kw)


_n = [0]


@pytest.fixture()
def signup():
    def make(org="Acme Rentals"):
        _n[0] += 1
        cl = Client()
        r = cl.post("/api/auth/signup", json={"org_name": org, "name": "Owner", "email": f"owner{_n[0]}@example.com", "password": PW})
        assert r.status_code == 200, r.text
        cl.refresh()
        cl.email = f"owner{_n[0]}@example.com"
        return cl
    return make


# ----------------------------------------------------------------------------- scripted mock model
def blueprint(cid):
    return {
        "summary": "An equipment-rental business that takes orders and handles refunds.",
        "industry": "Equipment rental", "business_model": "B2C rentals", "primary_users": ["Support agents", "Managers"],
        "ontology": [{"name": "Order", "description": "A rental order", "source": {"connection_id": cid, "table": "orders"}, "key_fields": ["order_id"]}],
        "facts": [{"name": "refund_amount", "type": "number", "description": "Amount to refund"},
                  {"name": "days_since_order", "type": "number", "description": "Days since the order"},
                  {"name": "damage_score", "type": "number", "description": "0..1 damage"}],
        "signals": [{"id": "damage_risk", "description": "Item damage", "inputs": [{"fact": "damage_score", "weight": 1}],
                     "assert_above": 0.7, "deny_below": 0.3}],
        "rules": [{"id": "refund_window", "description": "Refunds only within 30 days", "citation": "policy.md p.1",
                   "applies_to": ["ISSUE_REFUND"], "condition": {"path": "days_since_order", "op": "<=", "value": 30}},
                  {"id": "no_damage", "description": "No refund for damaged returns", "citation": "policy.md p.1",
                   "applies_to": ["ISSUE_REFUND"], "condition": {"path": "signals.damage_risk", "is": False}}],
        "actions": [{"name": "ISSUE_REFUND", "description": "Refund the customer", "risk": "HIGH", "amount_fact": "refund_amount",
                     "required_facts": ["refund_amount", "days_since_order"], "auto_approve_below": 500, "owner_role": "Reviewer",
                     "executor": {"type": "webhook"}},
                    {"name": "MARK_REFUNDED", "description": "Set the order status to refunded", "risk": "LOW", "owner_role": "Reviewer",
                     "executor": {"type": "database", "connection_id": cid, "table": "orders", "operation": "update",
                                  "key_column": "order_id", "columns": ["status"]}}],
        "agents": [{"id": "support_analyst", "name": "Support Analyst", "purpose": "Investigates orders and refunds",
                    "instructions": "Look up orders.", "tools": ["query_data", "search_knowledge", "check_rules"],
                    "data_scope": [{"connection_id": cid, "tables": ["orders"]}], "actions": ["ISSUE_REFUND"]}],
        "watch_rules": [{"id": "large_refund_request", "event_type": "refund.*", "when": {"path": "data.amount", "op": ">=", "value": 500},
                         "why": "Large refund requests may need action", "owner_role": "Reviewer"}],
        "kpis": [{"name": "Refund rate", "description": "Refunds / orders"}],
        "starter_questions": ["Refund order 1001"],
    }


def _row_step(tool_msgs, oid, task):
    rows = json.loads(tool_msgs[0]["content"])["rows"]
    _, _, amount, days, damage, _status = rows[0]
    if "mark" in task.lower():
        return {"action": "MARK_REFUNDED", "facts": {}, "payload": {"order_id": int(oid), "status": "refunded"}, "summary": f"Mark {oid} refunded"}
    return {"action": "ISSUE_REFUND", "facts": {"refund_amount": amount, "days_since_order": days, "damage_score": damage},
            "payload": {"order_id": int(oid)}, "summary": f"Refund order {oid}"}


def scripted(system, messages, tools):
    names = {t["name"] for t in tools or []}
    last = messages[-1]
    if not tools:
        return ChatResult(text="Aria XAI connection OK.", input_tokens=12, output_tokens=6)
    if "submit_blueprint" in names:
        cid = re.search(r'"connection_id": "(dc_[0-9a-f]+)"', messages[0]["content"])
        return ChatResult(text="", tool_calls=[ToolCall("tb1", "submit_blueprint", blueprint(cid.group(1) if cid else "dc_x"))], stop="tool_use")
    task = messages[0]["content"]
    oid = (re.search(r"\b(\d{4})\b", task) or [None, "1001"])[1]
    tool_msgs = [m for m in messages if m["role"] == "tool"]
    cid = (re.search(r"connection (dc_[0-9a-f]+)", system) or [None, "dc_x"])[1]
    if "suggest_change" in names:  # Aria Watch
        if not tool_msgs:
            return ChatResult(text="", tool_calls=[ToolCall("w1", "query_data", {"connection_id": cid, "sql": f"SELECT * FROM orders WHERE order_id = {oid}"})], stop="tool_use")
        step = _row_step(tool_msgs, oid, "")
        return ChatResult(text="", tool_calls=[ToolCall("w2", "suggest_change", {"title": f"Refund order {oid}", "rationale": "Within policy",
                                                                                   "benefit": "Keeps the customer", "steps": [step]})], stop="tool_use")
    if "propose_plan" in names:  # Aria Executor
        if not tool_msgs:
            return ChatResult(text="", tool_calls=[ToolCall("q1", "query_data", {"connection_id": cid, "sql": f"SELECT * FROM orders WHERE order_id = {oid}"})], stop="tool_use")
        if len(tool_msgs) == 1:
            return ChatResult(text="", tool_calls=[ToolCall("p1", "propose_plan", {"title": f"Order {oid}", "summary": "As requested",
                                                                                   "steps": [_row_step(tool_msgs, oid, task)]})], stop="tool_use")
        return ChatResult(text="Plan proposed: " + tool_msgs[-1]["content"][:200])
    if "delegate" in names and "You are Aria Orchestrator" in system:
        if last["role"] == "user":
            lead = "executor" if re.search(r"\b(refund|mark|update|change)\b", last["content"], re.I) else "analyst"
            return ChatResult(text="", tool_calls=[ToolCall("d1", "delegate", {"agent_id": lead, "task": last["content"]})], stop="tool_use")
        return ChatResult(text="Done. " + last["content"][:400])
    return ChatResult(text="Report: nothing further.")


@pytest.fixture(autouse=True)
def _script():
    MockProvider.script = staticmethod(scripted)
    yield
    MockProvider.script = None


@pytest.fixture(scope="session", autouse=True)
def _cleanup():
    yield
    shutil.rmtree(_TMP, ignore_errors=True)
