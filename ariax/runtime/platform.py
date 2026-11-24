"""Platform composition. Composition upward, never sideways: every subsystem may consume another,
no subsystem hands a product a way around another."""
import json
from pathlib import Path

from ..connectors import ConnectorSDK, SecretStore
from ..core.bundle import BundleService, Signer
from ..core.errors import NotFound
from ..core.identity import Principal
from ..core.store import Store
from ..fabric import KnowledgeFabric
from ..rules import RuleEngine
from ..sentinel import Sentinel
from .chat import AgentChat
from .runner import AgentRunner

ROOT = Path(__file__).resolve().parents[2]


class Platform:
    def __init__(self, data_dir: Path | str = ROOT / "data", bundles_dir: Path | str = ROOT / "examples" / "bundles"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.bundles_dir = Path(bundles_dir)
        self.store = Store(str(self.data_dir / "platform.db"))
        self.signer = Signer(self.data_dir / ".signing_key")
        self.bundles = BundleService(self.store, self.signer, self.bundles_dir)
        self.connectors = ConnectorSDK(self.store, SecretStore(self.data_dir / "secrets.json"), str(self.data_dir / "fabric.db"))
        self.fabric = KnowledgeFabric(self.connectors, self.bundles)
        self.rules = RuleEngine()
        self.sentinel = Sentinel(self.store, self.connectors, self.bundles)
        self.runner = AgentRunner(self)
        self.chat = AgentChat(self)
        self.bundles.on_activate(self._on_activate)
        self.bundles.seed_from_disk()

    def _on_activate(self, domain: str, bundle: dict):
        self.connectors.load_bundle(domain, bundle)
        self._seed_facts(domain, bundle)

    def _seed_facts(self, domain, bundle):
        tenant = bundle["manifest"]["tenant"]
        ingest = Principal(tenant=tenant, service=domain, agent="ingestion")
        ids = {}
        facts = (bundle.get("fabric") or {}).get("seed_facts") or []
        for f in facts:
            ev = {k: f.get(k) for k in ("entity", "subject", "predicate", "value", "effective_from", "effective_to", "published_at", "ingested_at", "case_id")}
            ev["predicate"] = ev.get("predicate") or "value"
            ids[f.get("key") or id(f)] = self.fabric.remember(ev, f["source"], ingest)["id"]
        for f in facts:
            if f.get("superseded_by_key") and f.get("key"):
                try:
                    self.fabric.invalidate(ids[f["key"]], ids.get(f["superseded_by_key"]), at=f.get("invalidated_at"))
                except NotFound:
                    pass  # already invalidated on a previous boot

    def auditor(self, domain: str) -> Principal:
        b = self.bundles.active(domain)
        return Principal(tenant=b["manifest"]["tenant"], service=domain, agent="auditor")

    def decision_join(self, decision_id: str) -> dict:
        """§03.2, given one decision_id: what did it see, how did it conclude, was it allowed, what did it touch."""
        dec = self.sentinel.decision(decision_id)
        if not dec:
            raise NotFound(f"No decision {decision_id}")
        ex = self.store.one("SELECT * FROM explanations WHERE decision_id=?", (decision_id,))
        receipts = []
        try:
            receipts = self.fabric.receipts(self.auditor(dec["domain"]), decision_id=decision_id)
        except Exception:  # noqa: BLE001
            pass
        run = self.store.one("SELECT run_id, trace_id, agent, case_id, status, verdict, outcome, score FROM runs WHERE decision_id=?", (decision_id,))
        return {
            "decision_id": decision_id,
            "decision": dec,
            "sentinel_audit": self.sentinel.ledger.rows(decision_id=decision_id),
            "receipts": receipts,
            "explanation": json.loads(ex["body"]) if ex else None,
            "connector_audit": self.connectors.audit_rows(trace_id=dec["trace_id"]),
            "run": run,
            "questions": {
                "sentinel.audit": "Was this permitted, under which rule and version?",
                "fabric.receipt": "What evidence was in front of the agent?",
                "rules.explanation": "How did that evidence become a conclusion?",
                "connector.audit": "Which credential reached which system?",
            },
        }

    def overview(self) -> dict:
        domains = []
        for d, b in self.bundles.active_domains().items():
            m = b["manifest"]
            domains.append({"domain": d, "name": m.get("name"), "version": m.get("version"), "tenant": m.get("tenant"),
                            "description": m.get("description"), "icon": m.get("icon"), "color": m.get("color"),
                            "agents": len((b.get("agents") or {}).get("agents") or []),
                            "entities": len((b.get("ontology") or {}).get("entities") or {}),
                            "connectors": len((b.get("connectors") or {}).get("instances") or []),
                            "hard_rules": len((b.get("rules") or {}).get("hard") or []),
                            "actions": len((b.get("policies") or {}).get("actions") or [])})
        c = lambda sql: self.store.one(sql)["n"]  # noqa: E731
        return {
            "domains": domains,
            "rejected_bundles": self.bundles.rejected,
            "counts": {"runs": c("SELECT COUNT(*) n FROM runs"), "decisions": c("SELECT COUNT(*) n FROM decisions"),
                       "pending_reviews": c("SELECT COUNT(*) n FROM decisions WHERE status='PENDING_REVIEW'"),
                       "audit_entries": c("SELECT COUNT(*) n FROM sentinel_audit"),
                       "connector_calls": c("SELECT COUNT(*) n FROM connector_audit"),
                       "transmissions": c("SELECT COUNT(*) n FROM outbox")},
            "fabric": self.fabric.stats(),
            "model": self.sentinel.gateway.status(),
            "kill_switches": self.sentinel.kill_switches(),
            "chain": self.sentinel.ledger.verify(),
        }
