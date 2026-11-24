"""Sentinel, how the system is constrained and audited.

Rails + risk fork + control plane:
    LOW risk        → answered locally from the cached policy (still recorded)
    MEDIUM / HIGH   → the Control Plane evaluates agent card, action card and policy statements
Effects: ALLOW / REVIEW / BLOCK. Default deny. Sentinel mints the decision_id that every other
record of the moment carries, and only an executable decision opens the egress connector.
"""
import json

from ..core import expr
from ..core.errors import KillSwitchEngaged, NotFound
from ..core.ids import canonical, new_decision_id, now_iso, sha256
from .gateway import ModelGateway
from .ledger import Ledger

EFFECT_ORDER = {"BLOCK": 3, "REVIEW": 2, "ALLOW": 1}


class Sentinel:
    def __init__(self, store, connectors, bundles):
        self.store, self.connectors, self.bundles = store, connectors, bundles
        self.ledger = Ledger(store)
        self.gateway = ModelGateway(self.ledger)
        store.executescript("""
        CREATE TABLE IF NOT EXISTS decisions (decision_id TEXT PRIMARY KEY, trace_id TEXT, domain TEXT, tenant TEXT,
            agent TEXT, case_id TEXT, action TEXT, risk TEXT, effect TEXT, status TEXT, amount REAL, payload TEXT,
            payload_hash TEXT, reasons TEXT, path TEXT, bundle_version TEXT, run_id TEXT, created_at TEXT,
            updated_at TEXT, reviewer TEXT, review_note TEXT, transmission_id TEXT, principal TEXT);
        CREATE TABLE IF NOT EXISTS kill_switches (scope TEXT PRIMARY KEY, engaged INTEGER, by TEXT, at TEXT, reason TEXT);
        """)
        connectors.decision_check = self._decision_check

    # ------------------------------------------------------------------ kill switch
    def kill_switches(self):
        return self.store.all("SELECT * FROM kill_switches WHERE engaged=1")

    def set_kill_switch(self, scope: str, engaged: bool, by: str, reason: str = ""):
        self.store.execute("INSERT OR REPLACE INTO kill_switches VALUES (?,?,?,?,?)", (scope, int(engaged), by, now_iso(), reason))
        self.ledger.append("kill_switch", None, detail={"scope": scope, "engaged": engaged, "by": by, "reason": reason})

    def _killed(self, domain, agent):
        engaged = {r["scope"] for r in self.kill_switches()}
        return next((s for s in ("global", f"domain:{domain}", f"agent:{domain}:{agent}") if s in engaged), None)

    def assert_alive(self, domain, agent):
        k = self._killed(domain, agent)
        if k:
            raise KillSwitchEngaged(f"Kill switch engaged ({k})")

    # ------------------------------------------------------------------ the decision
    def evaluate(self, bundle: dict, agent_card: dict, action_name: str, ctx: dict) -> dict:
        pol = bundle.get("policies") or {}
        action = next((a for a in pol.get("actions") or [] if a["name"] == action_name), None)
        reasons, matched = [], []
        if not action:
            return {"effect": "BLOCK", "reasons": [f"action '{action_name}' is not declared (default deny)"], "path": "control-plane", "risk": "HIGH", "matched": []}
        risk = action["risk"]
        path = "local-cache" if risk == "LOW" else "control-plane"
        killed = self._killed(bundle["manifest"]["domain"], agent_card.get("id"))
        if killed:
            return {"effect": "BLOCK", "reasons": [f"kill switch engaged: {killed}"], "path": path, "risk": risk, "matched": ["kill-switch"]}
        if action_name not in (agent_card.get("allowed_actions") or []):
            return {"effect": "BLOCK", "reasons": [f"agent '{agent_card.get('id')}' is not certified for {action_name}"], "path": path, "risk": risk, "matched": ["agent-card"]}
        if risk != "LOW" and not agent_card.get("certified"):
            return {"effect": "BLOCK", "reasons": [f"agent '{agent_card.get('id')}' is not certified for {risk} actions"], "path": path, "risk": risk, "matched": ["agent-card"]}
        effect = None
        limit = (agent_card.get("limits") or {}).get("max_amount")
        if limit is not None and ctx.get("amount") is not None and ctx["amount"] > limit:
            effect = "REVIEW"
            reasons.append(f"amount {ctx['amount']} exceeds agent limit {limit}")
            matched.append("agent-limit")
        ectx = {**ctx, "action": action, "agent": agent_card}
        for st in pol.get("statements") or []:
            if "*" not in st.get("actions", []) and action_name not in st.get("actions", []):
                continue
            res, _ = expr.evaluate(st.get("when"), ectx)
            if res is True:
                matched.append(st["id"])
                reasons.append(st.get("reason") or f"{st['id']} → {st['effect']}")
                if effect is None or EFFECT_ORDER[st["effect"]] > EFFECT_ORDER[effect]:
                    effect = st["effect"]
        if effect is None:
            effect = pol.get("default", "BLOCK")
            reasons.append("no statement allowed this action (default deny)")
        return {"effect": effect, "reasons": reasons, "path": path, "risk": risk, "matched": matched, "action": action}

    def governed_step(self, *, principal, bundle: dict, agent_card: dict, action_name: str, payload: dict,
                      amount=None, verdict=None, signals=None, run_id=None, evidence_hook=None) -> dict:
        """The governed wrapper: decide, record, and only on ALLOW carry the action out.
        evidence_hook(decision_id) lets the Fabric write its receipt and the Rule Engine link its
        explanation under the same decision_id before anything leaves the process (§03.2)."""
        domain, version = bundle["manifest"]["domain"], bundle["manifest"]["version"]
        decision_id = new_decision_id()
        if evidence_hook:
            evidence_hook(decision_id)
        ctx = {"amount": amount, "verdict": verdict, "signals": signals or {}, "case": principal.case}
        d = self.evaluate(bundle, agent_card, action_name, ctx)
        ph = sha256(canonical(payload))
        status = {"ALLOW": "ALLOWED", "REVIEW": "PENDING_REVIEW", "BLOCK": "BLOCKED"}[d["effect"]]
        self.store.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            decision_id, principal.trace_id, domain, principal.tenant, principal.agent, principal.case, action_name,
            d["risk"], d["effect"], status, amount, json.dumps(payload, default=str), ph, json.dumps(d["reasons"]), d["path"],
            version, run_id, now_iso(), now_iso(), None, None, None, json.dumps(principal.to_dict())))
        self.ledger.append("decision", principal, decision_id, action_name, d["effect"], ",".join(d["matched"]), version,
                           {"risk": d["risk"], "path": d["path"], "reasons": d["reasons"], "amount": amount, "verdict": verdict, "payload_hash": ph})
        result = {"decision_id": decision_id, "effect": d["effect"], "status": status, "risk": d["risk"], "path": d["path"],
                  "reasons": d["reasons"], "matched": d["matched"], "transmission": None}
        if d["effect"] == "ALLOW":
            result["transmission"] = self._execute(decision_id, principal, bundle)
            result["status"] = "EXECUTED"
        return result

    def _execute(self, decision_id, principal, bundle):
        dec = self.store.one("SELECT * FROM decisions WHERE decision_id=?", (decision_id,))
        action = next((a for a in bundle["policies"]["actions"] if a["name"] == dec["action"]), {})
        if not action.get("connector"):
            tx = {"transmission_id": None, "note": "internal action, no external system touched"}
        else:
            handle = self.connectors.get(action["connector"], principal, domain=dec["domain"])
            tx = handle.invoke(action.get("operation", dec["action"].lower()), json.loads(dec["payload"]), decision_id=decision_id)
        self.store.execute("UPDATE decisions SET status='EXECUTED', transmission_id=?, updated_at=? WHERE decision_id=?",
                           (tx.get("transmission_id"), now_iso(), decision_id))
        self.ledger.append("execution", principal, decision_id, dec["action"], dec["effect"], None, dec["bundle_version"], tx)
        return tx

    def _decision_check(self, decision_id, domain, connector, operation):
        dec = self.store.one("SELECT * FROM decisions WHERE decision_id=?", (decision_id,))
        if not dec:
            return False, "unknown decision"
        if dec["domain"] != domain:
            return False, "decision belongs to another domain"
        if dec["status"] not in ("ALLOWED", "APPROVED"):
            return False, f"decision status is {dec['status']}"
        bundle = self.bundles.active(domain)
        action = next((a for a in bundle["policies"]["actions"] if a["name"] == dec["action"]), {})
        if action.get("connector") != connector:
            return False, f"decision authorises {action.get('connector')}, not {connector}"
        return True, "ok"

    # ------------------------------------------------------------------ human review
    def reviews(self, status="PENDING_REVIEW"):
        rows = self.store.all("SELECT * FROM decisions WHERE status=? ORDER BY created_at DESC" if status else
                              "SELECT * FROM decisions ORDER BY created_at DESC LIMIT 200", (status,) if status else ())
        for r in rows:
            r["payload"] = json.loads(r["payload"]) if r["payload"] else None
            r["reasons"] = json.loads(r["reasons"]) if r["reasons"] else []
        return rows

    def review(self, decision_id: str, approve: bool, reviewer: str, note: str = "") -> dict:
        from ..core.identity import Principal
        dec = self.store.one("SELECT * FROM decisions WHERE decision_id=?", (decision_id,))
        if not dec:
            raise NotFound(f"No decision {decision_id}")
        if dec["status"] != "PENDING_REVIEW":
            raise NotFound(f"Decision {decision_id} is {dec['status']}, not pending review")
        p = json.loads(dec["principal"])
        principal = Principal(tenant=p["tenant"], service=p["service"], agent=p["agent"], case=p["case"],
                              on_behalf_of=p["on_behalf_of"], trace_id=p["trace_id"])
        status = "APPROVED" if approve else "REJECTED"
        self.store.execute("UPDATE decisions SET status=?, reviewer=?, review_note=?, updated_at=? WHERE decision_id=?",
                           (status, reviewer, note, now_iso(), decision_id))
        self.ledger.append("review", principal, decision_id, dec["action"], status, "human-review", dec["bundle_version"],
                           {"reviewer": reviewer, "note": note})
        out = {"decision_id": decision_id, "status": status}
        if approve:
            out["transmission"] = self._execute(decision_id, principal, self.bundles.active(dec["domain"]))
            out["status"] = "EXECUTED"
        return out

    def decision(self, decision_id):
        r = self.store.one("SELECT * FROM decisions WHERE decision_id=?", (decision_id,))
        if r:
            r["payload"] = json.loads(r["payload"]) if r["payload"] else None
            r["reasons"] = json.loads(r["reasons"]) if r["reasons"] else []
        return r

    # ------------------------------------------------------------------ watchdog
    def watchdog(self) -> dict:
        """Reconcile what the outside world received against what was approved."""
        incidents = []
        sent = self.connectors.outbox.rows(1000)
        for tx in sent:
            if not tx["decision_id"]:
                incidents.append({"severity": "critical", "transmission_id": tx["id"], "connector": tx["connector"],
                                  "issue": "transmission without a decision_id", "via": tx["via"], "at": tx["sent_at"]})
                continue
            dec = self.store.one("SELECT * FROM decisions WHERE decision_id=?", (tx["decision_id"],))
            if not dec:
                incidents.append({"severity": "critical", "transmission_id": tx["id"], "issue": "decision_id not found in ledger", "at": tx["sent_at"]})
            elif dec["status"] != "EXECUTED" or dec["transmission_id"] != tx["id"]:
                incidents.append({"severity": "high", "transmission_id": tx["id"], "issue": f"decision status {dec['status']} does not match transmission", "at": tx["sent_at"]})
            elif dec["payload_hash"] != tx["payload_hash"]:
                incidents.append({"severity": "high", "transmission_id": tx["id"], "issue": "payload differs from the approved payload", "at": tx["sent_at"]})
        return {"checked": len(sent), "incidents": incidents, "at": now_iso()}
