"""Knowledge Fabric, how the system remembers.

The requirement everything follows from: reconstruct not just what was true, but what the system
believed at the moment it acted.

Short-term memory: per-trace working memory (scratchpad, TTL), never shared.
Long-term memory: the four tiers, facts, episodes, receipts, provenance.

Eight methods (the interface):
    read:   query(q, principal, as_known_at)   provenance(item_id)   subscribe(filter, fn)
    write:  remember(event, source, principal) checkpoint(case, state, principal)
            promote(item, to_tier, evidence)   invalidate(fact_id, superseded_by)
            forget(subject_id, reason)
"""
import json
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..core.errors import NotAuthorized, NotFound
from ..core.identity import Principal, fabric_principal
from ..core.ids import canonical, new_id, now_iso, sha256

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


def norm_date(d) -> str | None:
    if d in (None, ""):
        return None
    s = str(d)
    if len(s) == 10:
        return s + "T00:00:00Z"
    return s.replace("+00:00", "Z")


class WorkingMemory:
    """Short-term memory: scoped to one trace, expires, never written to shared memory."""

    def __init__(self, ttl_seconds=3600):
        self.ttl, self._d, self._lock = ttl_seconds, {}, threading.Lock()

    def put(self, trace_id, key, value):
        with self._lock:
            slot = self._d.setdefault(trace_id, {"items": {}, "expires": 0})
            slot["items"][key] = value
            slot["expires"] = time.time() + self.ttl

    def get(self, trace_id):
        with self._lock:
            self._d = {k: v for k, v in self._d.items() if v["expires"] > time.time()}
            return dict(self._d.get(trace_id, {}).get("items", {}))

    def stats(self):
        with self._lock:
            live = {k: v for k, v in self._d.items() if v["expires"] > time.time()}
            return {"active_traces": len(live), "items": sum(len(v["items"]) for v in live.values()), "ttl_seconds": self.ttl}


class KnowledgeFabric:
    def __init__(self, connectors, bundles):
        self.bundles = bundles
        # §03.4, the Fabric consumes connectors; its own handle comes from the connector layer.
        handle = connectors.get("fabric-store", fabric_principal("platform"), domain="_platform")
        self.conn, self.lock = handle.pooled()
        with self.lock:
            self.conn.executescript(SCHEMA)
        self.short_term = WorkingMemory()
        self._subs = []

    # ------------------------------------------------------------------ identity → scope
    def role_for(self, principal: Principal) -> dict:
        bundle = self.bundles.active(principal.service)
        for r in (bundle.get("fabric") or {}).get("roles") or []:
            if r.get("agent") == principal.agent:
                return r
        raise NotAuthorized(f"No Fabric role for agent '{principal.agent}' in '{principal.service}'")

    @contextmanager
    def _scoped(self, principal: Principal):
        role = self.role_for(principal)
        if role["scope"] == "case" and not principal.case:
            raise NotAuthorized("A case-scoped role must declare a case")
        with self.lock:
            self.conn.execute("BEGIN")
            try:
                self.conn.execute("INSERT INTO session_ctx VALUES (?,?,?,?,?,?)", (
                    principal.tenant, principal.service, principal.case, role["scope"],
                    ",".join(role.get("entities") or []), principal.agent))
                yield role
            finally:
                self.conn.execute("ROLLBACK")  # the identity row never outlives the transaction

    def _rows(self, sql, params=()):
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    # ------------------------------------------------------------------ read
    def query(self, q: dict, principal: Principal, as_known_at: str | None = None, valid_at: str | None = None, limit=50) -> list[dict]:
        """Returns Answers: value + source (required) + valid (world time) + known_at (system time) + visible_to."""
        t = norm_date(as_known_at) or now_iso()
        sql = ["SELECT f.*, p.source, p.locator, p.ingest_job FROM facts f JOIN _provenance p ON p.id = f.provenance_id",
               "WHERE f.ingested_at <= ? AND (f.invalidated_at IS NULL OR f.invalidated_at > ?)"]
        params = [t, t]
        if valid_at:
            v = norm_date(valid_at)
            sql.append("AND f.effective_from <= ? AND (f.effective_to IS NULL OR f.effective_to > ?)")
            params += [v, v]
        for k in ("entity", "subject", "predicate"):
            if q.get(k):
                sql.append(f"AND f.{k} = ?")
                params.append(q[k])
        if q.get("text"):
            sql.append("AND (f.subject LIKE ? OR f.value LIKE ? OR f.predicate LIKE ?)")
            params += [f"%{q['text']}%"] * 3
        sql.append("ORDER BY f.effective_from DESC, f.ingested_at DESC LIMIT ?")
        params.append(limit)
        with self._scoped(principal) as role:
            rows = self._rows(" ".join(sql), params)
        return [self._answer(r, principal, role, t) for r in rows]

    def _answer(self, r, principal, role, t):
        return {
            "id": r["id"], "entity": r["entity"], "subject": r["subject"], "predicate": r["predicate"],
            "value": json.loads(r["value"]) if r["value"] else None, "case_id": r["case_id"],
            "source": {"source": r["source"], "locator": r["locator"], "ingest_job": r["ingest_job"], "provenance_id": r["provenance_id"]},
            "valid": {"from": r["effective_from"], "to": r["effective_to"]},
            "known_at": {"published_at": r["published_at"], "ingested_at": r["ingested_at"], "invalidated_at": r["invalidated_at"],
                         "superseded_by": r["superseded_by"], "as_known_at": t},
            "lag_days": _days(r["published_at"], r["ingested_at"]),
            "visible_to": {"agent": principal.agent, "scope": role["scope"], "case": principal.case,
                           "reason": f"role '{role['agent']}' may read {r['entity']} ({role['scope']} scope)"},
        }

    def all_facts(self, principal: Principal, include_invalidated=True, limit=500) -> list[dict]:
        with self._scoped(principal) as role:
            rows = self._rows("SELECT f.*, p.source, p.locator, p.ingest_job FROM facts f JOIN _provenance p ON p.id=f.provenance_id "
                              + ("" if include_invalidated else "WHERE f.invalidated_at IS NULL ")
                              + "ORDER BY f.entity, f.subject, f.ingested_at LIMIT ?", (limit,))
        return [self._answer(r, principal, role, now_iso()) for r in rows]

    def provenance(self, item_id: str) -> dict:
        with self.lock:
            f = self.conn.execute("SELECT * FROM _facts WHERE id=?", (item_id,)).fetchone()
            if not f:
                raise NotFound(f"No fact {item_id}")
            chain, cur = [], dict(f)
            seen = set()
            while cur and cur["id"] not in seen:
                seen.add(cur["id"])
                p = dict(self.conn.execute("SELECT * FROM _provenance WHERE id=?", (cur["provenance_id"],)).fetchone())
                chain.append({"fact": {k: cur[k] for k in ("id", "subject", "predicate", "value", "effective_from", "published_at", "ingested_at", "invalidated_at", "superseded_by")}, "provenance": p})
                prev = self.conn.execute("SELECT * FROM _facts WHERE superseded_by=?", (cur["id"],)).fetchone()
                cur = dict(prev) if prev else None
        return {"item_id": item_id, "chain": chain}

    def subscribe(self, fn, filter_kind: str | None = None):
        self._subs.append((filter_kind, fn))

    def episodes(self, principal: Principal, limit=500) -> list[dict]:
        with self._scoped(principal):
            rows = self._rows("SELECT * FROM episodes ORDER BY seq DESC LIMIT ?", (limit,))
        for r in rows:
            r["data"] = json.loads(r["data"]) if r["data"] else None
        return rows

    def receipts(self, principal: Principal, decision_id: str | None = None, limit=200) -> list[dict]:
        with self._scoped(principal):
            if decision_id:
                rows = self._rows("SELECT * FROM receipts WHERE decision_id=?", (decision_id,))
            else:
                rows = self._rows("SELECT * FROM receipts ORDER BY at DESC LIMIT ?", (limit,))
        for r in rows:
            for k in ("shown", "passed_over", "conditions"):
                r[k] = json.loads(r[k]) if r[k] else None
        return rows

    # ------------------------------------------------------------------ write
    def remember(self, event: dict, source: dict, principal: Principal) -> dict:
        """Ingestion → facts. Every fact carries provenance; there is no default source."""
        if not source or not source.get("source"):
            raise ValueError("remember() requires a source, no fact without provenance")
        if principal.agent != "ingestion":  # the acquisition pipeline's identity
            role = self.role_for(principal)
            if event["entity"] not in (role.get("write") or []):
                raise NotAuthorized(f"agent '{principal.agent}' may not write {event['entity']} facts")
        nk = sha256(canonical([principal.tenant, principal.service, event.get("case_id"), event["entity"], event["subject"],
                               event.get("predicate", "value"), event.get("value"), norm_date(event.get("effective_from"))]))
        with self.lock:
            existing = self.conn.execute("SELECT id FROM _facts WHERE natural_key=?", (nk,)).fetchone()
            if existing:
                return {"id": existing["id"], "deduplicated": True}
            pid, fid = new_id("pv"), new_id("ft")
            self.conn.execute("INSERT INTO _provenance VALUES (?,?,?,?,?)",
                              (pid, source["source"], source.get("locator"), source.get("ingest_job"), now_iso()))
            ingested = norm_date(event.get("ingested_at")) or now_iso()
            self.conn.execute("INSERT INTO _facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                fid, principal.tenant, principal.service, event.get("case_id"), event["entity"], event["subject"],
                event.get("predicate", "value"), json.dumps(event.get("value"), default=str),
                norm_date(event.get("effective_from")) or ingested, norm_date(event.get("effective_to")),
                norm_date(event.get("published_at")) or ingested, ingested,
                norm_date(event.get("invalidated_at")), event.get("superseded_by"), pid, nk))
        return {"id": fid, "provenance_id": pid}

    def record_episode(self, principal: Principal, kind: str, observation=None, action=None, outcome=None,
                       decision_id=None, data=None) -> str:
        """Agent → episodes. Automatic, every step, trajectory-shaped. Append only."""
        eid = new_id("ep")
        with self.lock:
            seq = (self.conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM _episodes").fetchone()[0])
            self.conn.execute("INSERT INTO _episodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                eid, seq, principal.tenant, principal.service, principal.case, principal.agent, principal.trace_id,
                decision_id, kind, _s(observation), _s(action), principal.agent, _s(outcome),
                json.dumps(data, default=str) if data is not None else None, now_iso()))
        for k, fn in self._subs:
            if k in (None, kind):
                try:
                    fn({"id": eid, "kind": kind, "principal": principal, "outcome": outcome, "data": data})
                except Exception:  # noqa: BLE001, a subscriber must never break the writer
                    pass
        return eid

    def checkpoint(self, case: str, state: dict, principal: Principal) -> str:
        return self.record_episode(principal.with_case(case) if case != principal.case else principal,
                                   "checkpoint", observation="state checkpoint", data=state)

    def write_receipt(self, principal: Principal, decision_id: str, shown: list, passed_over: list, conditions: dict,
                      retention_days: int = 90) -> dict:
        """Agent → receipts, at decisions the bundle declares: content of what was used, ids of what was passed over,
        plus the conditions the search ran under. Hashed."""
        body = {"decision_id": decision_id, "shown": shown, "passed_over": passed_over, "conditions": conditions}
        h = sha256(canonical(body))
        rid = new_id("rc")
        expires = (datetime.now(timezone.utc) + timedelta(days=retention_days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        with self.lock:
            self.conn.execute("INSERT INTO _receipts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                rid, principal.tenant, principal.service, principal.case, principal.agent, principal.trace_id, decision_id,
                json.dumps(shown, default=str), json.dumps(passed_over, default=str), json.dumps(conditions, default=str),
                h, now_iso(), expires))
        return {"receipt_id": rid, "hash": h, "expires_at": expires}

    def invalidate(self, fact_id: str, superseded_by: str | None, at: str | None = None):
        with self.lock:
            cur = self.conn.execute("UPDATE _facts SET invalidated_at=?, superseded_by=? WHERE id=? AND invalidated_at IS NULL",
                                    (norm_date(at) or now_iso(), superseded_by, fact_id))
            if cur.rowcount == 0:
                raise NotFound(f"No current fact {fact_id}")

    def forget(self, subject_id: str, reason: str, principal: Principal) -> int:
        """Erasure request: values are redacted in place; the tombstone (and the fact that we forgot) remains."""
        with self.lock:
            n = self.conn.execute("UPDATE _facts SET value=?, invalidated_at=COALESCE(invalidated_at, ?) WHERE subject=? AND tenant=? AND domain=?",
                                  (json.dumps({"forgotten": True, "reason": reason}), now_iso(), subject_id, principal.tenant, principal.service)).rowcount
        self.record_episode(principal, "forget", observation=f"erasure of subject {subject_id}", action="forget", outcome=f"{n} facts redacted", data={"reason": reason})
        return n

    # ------------------------------------------------------------------ reflection → proposals → gate
    def reflect(self, principal: Principal) -> list[dict]:
        """Reflection subscribes to episodes and PROPOSES; it never writes facts.
        Outcome rates per (agent, action) become candidate Insight facts that must pass the gate."""
        bundle = self.bundles.active(principal.service)
        cfg = (bundle.get("fabric") or {}).get("reflection") or {}
        entity, min_ev = cfg.get("entity", "Insight"), int(cfg.get("min_evidence", 3))
        with self.lock:
            rows = self._rows("SELECT agent, action, outcome, COUNT(*) n, GROUP_CONCAT(id) ids FROM _episodes "
                              "WHERE tenant=? AND domain=? AND kind='outcome' GROUP BY agent, action, outcome",
                              (principal.tenant, principal.service))
        totals = {}
        for r in rows:
            totals[(r["agent"], r["action"])] = totals.get((r["agent"], r["action"]), 0) + r["n"]
        out = []
        for r in rows:
            total = totals[(r["agent"], r["action"])]
            subject = f"{r['agent']}:{r['action']}"
            value = {"outcome": r["outcome"], "rate": round(r["n"] / total, 3), "observations": total}
            if total < min_ev:
                gate = "INSUFFICIENT_EVIDENCE"
            else:
                gate = "PROPOSED"
            with self.lock:
                exists = self.conn.execute("SELECT id FROM _proposals WHERE tenant=? AND domain=? AND subject=? AND predicate=? AND status='pending'",
                                           (principal.tenant, principal.service, subject, f"outcome_rate:{r['outcome']}")).fetchone()
                if exists:
                    self.conn.execute("UPDATE _proposals SET value=?, evidence_count=?, evidence=?, gate_outcome=? WHERE id=?",
                                      (json.dumps(value), total, r["ids"], gate, exists["id"]))
                    pid = exists["id"]
                else:
                    pid = new_id("pp")
                    self.conn.execute("INSERT INTO _proposals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                        pid, principal.tenant, principal.service, entity, subject, f"outcome_rate:{r['outcome']}",
                        json.dumps(value), total, r["ids"], gate, "pending", None, None, now_iso()))
            out.append({"id": pid, "subject": subject, "value": value, "gate": gate})
        return out

    def proposals(self, tenant: str, domain: str) -> list[dict]:
        with self.lock:
            rows = self._rows("SELECT * FROM _proposals WHERE tenant=? AND domain=? ORDER BY created_at DESC", (tenant, domain))
        for r in rows:
            r["value"] = json.loads(r["value"]) if r["value"] else None
            r["evidence"] = (r["evidence"] or "").split(",")[:20]
        return rows

    def promote(self, proposal_id: str, approver: str, approve: bool) -> dict:
        """The promotion gate: evidence threshold, source required, contradiction check, human approval."""
        with self.lock:
            p = self.conn.execute("SELECT * FROM _proposals WHERE id=?", (proposal_id,)).fetchone()
        if not p:
            raise NotFound(f"No proposal {proposal_id}")
        p = dict(p)
        if not approve:
            status = "rejected"
            result = {"id": proposal_id, "status": status}
        else:
            if p["gate_outcome"] != "PROPOSED":
                raise NotAuthorized(f"Proposal gate outcome is {p['gate_outcome']}; it cannot be promoted")
            fp = Principal(tenant=p["tenant"], service=p["domain"], agent="ingestion")
            res = self.remember({"entity": p["entity"], "subject": p["subject"], "predicate": p["predicate"],
                                 "value": json.loads(p["value"])},
                                {"source": "reflection", "locator": proposal_id, "ingest_job": f"approved-by:{approver}"}, fp)
            status = "promoted"
            result = {"id": proposal_id, "status": status, "fact_id": res["id"]}
        with self.lock:
            self.conn.execute("UPDATE _proposals SET status=?, decided_by=?, decided_at=? WHERE id=?", (status, approver, now_iso(), proposal_id))
        return result

    # ------------------------------------------------------------------ stats
    def stats(self):
        with self.lock:
            c = lambda t: self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: E731
            return {"facts": c("_facts"), "episodes": c("_episodes"), "receipts": c("_receipts"),
                    "provenance": c("_provenance"), "proposals": c("_proposals"), "short_term": self.short_term.stats()}


def _s(v):
    if v is None or isinstance(v, str):
        return v
    return json.dumps(v, default=str)


def _days(a, b):
    try:
        da = datetime.fromisoformat(a.replace("Z", "+00:00"))
        db = datetime.fromisoformat(b.replace("Z", "+00:00"))
        return round((db - da).total_seconds() / 86400, 1)
    except Exception:  # noqa: BLE001
        return None
