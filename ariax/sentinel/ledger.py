"""Tamper-evident audit ledger (sentinel.audit). Each entry hashes the previous one, so any edit
to history breaks the chain and verify() reports exactly where."""
import json

from ..core.ids import canonical, now_iso, sha256

GENESIS = "0" * 64


class Ledger:
    def __init__(self, store):
        self.store = store
        store.executescript("""
        CREATE TABLE IF NOT EXISTS sentinel_audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, kind TEXT,
            decision_id TEXT, trace_id TEXT, principal TEXT, action TEXT, effect TEXT, rule TEXT,
            bundle_version TEXT, detail TEXT, prev_hash TEXT, hash TEXT);
        """)

    def append(self, kind, principal, decision_id=None, action=None, effect=None, rule=None, bundle_version=None, detail=None):
        with self.store.lock:
            prev = self.store.one("SELECT hash FROM sentinel_audit ORDER BY seq DESC LIMIT 1")
            prev_hash = prev["hash"] if prev else GENESIS
            row = {"at": now_iso(), "kind": kind, "decision_id": decision_id, "trace_id": getattr(principal, "trace_id", None),
                   "principal": principal.to_dict() if principal else None, "action": action, "effect": effect, "rule": rule,
                   "bundle_version": bundle_version, "detail": detail}
            h = sha256(prev_hash + canonical(row))
            self.store.execute("INSERT INTO sentinel_audit (at, kind, decision_id, trace_id, principal, action, effect, rule, bundle_version, detail, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                               (row["at"], kind, decision_id, row["trace_id"], json.dumps(row["principal"]), action, effect, rule,
                                bundle_version, json.dumps(detail, default=str), prev_hash, h))
            return h

    def rows(self, decision_id=None, limit=300):
        if decision_id:
            rows = self.store.all("SELECT * FROM sentinel_audit WHERE decision_id=? ORDER BY seq", (decision_id,))
        else:
            rows = self.store.all("SELECT * FROM sentinel_audit ORDER BY seq DESC LIMIT ?", (limit,))
        for r in rows:
            r["principal"] = json.loads(r["principal"]) if r["principal"] else None
            r["detail"] = json.loads(r["detail"]) if r["detail"] else None
        return rows

    def verify(self) -> dict:
        prev = GENESIS
        n = 0
        for r in self.store.all("SELECT * FROM sentinel_audit ORDER BY seq"):
            row = {"at": r["at"], "kind": r["kind"], "decision_id": r["decision_id"], "trace_id": r["trace_id"],
                   "principal": json.loads(r["principal"]) if r["principal"] else None, "action": r["action"],
                   "effect": r["effect"], "rule": r["rule"], "bundle_version": r["bundle_version"],
                   "detail": json.loads(r["detail"]) if r["detail"] else None}
            if r["prev_hash"] != prev or sha256(prev + canonical(row)) != r["hash"]:
                return {"ok": False, "entries": n, "broken_at_seq": r["seq"]}
            prev = r["hash"]
            n += 1
        return {"ok": True, "entries": n, "head": prev}
