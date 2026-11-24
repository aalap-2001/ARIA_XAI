"""Connector adapters. Each adapter knows a transport, never a domain.

In this reference build, systems of record (POS, CRM, ERP, core banking, FHIR,
REST APIs, JDBC databases) are served from the bundle's fixtures so the platform runs fully
offline / air-gapped. Swapping a fixture adapter for a live one is a registry change, not an
engine change: the SDK interface (resolve → invoke) is identical.
"""
import copy
import json
import sqlite3
import threading

from ..core.ids import canonical, new_id, now_iso, sha256

# Transport families the platform understands. A bundle picks one per instance.
ADAPTER_TYPES = {
    "rest": "HTTP/REST API",
    "graphql": "GraphQL API",
    "jdbc": "Relational DB (Postgres, MySQL, SQL Server, Oracle)",
    "kafka": "Event stream (Kafka / Kinesis / Pub-Sub)",
    "erp": "ERP (SAP, Oracle, Dynamics, NetSuite)",
    "crm": "CRM (Salesforce, HubSpot, Dynamics)",
    "pos": "Point of sale",
    "core-banking": "Banking ERP / core banking",
    "fhir": "Healthcare FHIR API",
    "document-store": "Document / content store",
    "egress": "Governed outbound action channel",
    "fabric-store": "Knowledge Fabric governed store",
}


class FixtureAdapter:
    """Serves records from bundle fixtures. Operation lookup: fixtures[op][key] or fixtures[op]['*']."""

    def __init__(self, instance: dict, fixtures: dict):
        self.instance = instance
        self.fixtures = fixtures or {}

    def invoke(self, operation: str, payload: dict):
        table = self.fixtures.get(operation)
        if table is None:
            raise KeyError(f"{self.instance['name']} has no operation '{operation}'")
        key = str(payload.get("key") or payload.get("case") or "")
        if isinstance(table, dict):
            if key in table:
                return copy.deepcopy(table[key])
            if "*" in table:
                return copy.deepcopy(table["*"])
            return None
        return copy.deepcopy(table)

    def raw(self):
        return self.fixtures


class StreamAdapter:
    """In-memory event stream with Kafka-like publish/consume semantics."""

    topics: dict[str, list] = {}
    _lock = threading.Lock()

    def __init__(self, instance: dict, fixtures: dict):
        self.instance = instance
        self.topic = instance.get("config", {}).get("topic", instance["name"])
        with self._lock:
            self.topics.setdefault(self.topic, list((fixtures or {}).get("seed", [])))

    def invoke(self, operation: str, payload: dict):
        with self._lock:
            if operation == "publish":
                evt = {"offset": len(self.topics[self.topic]), "at": now_iso(), "value": payload.get("value", payload)}
                self.topics[self.topic].append(evt)
                return evt
            if operation == "consume":
                return list(self.topics[self.topic][int(payload.get("offset", 0)):])
        raise KeyError(f"stream adapter supports publish/consume, not '{operation}'")

    def raw(self):
        return self.topics[self.topic]


class EgressAdapter:
    """The governed outbound path (clearinghouse, payment rail, e-signature, notification...).
    Every send lands in the outbox ledger, the 'network' the watchdog reconciles against."""

    def __init__(self, instance: dict, outbox):
        self.instance, self.outbox = instance, outbox

    def invoke(self, operation: str, payload: dict, decision_id: str | None = None):
        return self.outbox.record(self.instance["name"], operation, payload, decision_id)

    def raw(self):
        return self.outbox


class Outbox:
    """Stand-in for the network boundary. In production this is the egress proxy's log;
    the property that matters is that it is written by the transport, not the caller."""

    def __init__(self, store):
        self.store = store
        store.executescript("""
        CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, connector TEXT, operation TEXT,
            payload TEXT, payload_hash TEXT, decision_id TEXT, sent_at TEXT, via TEXT);
        """)

    def record(self, connector, operation, payload, decision_id, via="governed"):
        rid = new_id("tx")
        ph = sha256(canonical(payload))
        self.store.execute("INSERT INTO outbox VALUES (?,?,?,?,?,?,?,?)",
                           (rid, connector, operation, json.dumps(payload, default=str), ph, decision_id, now_iso(), via))
        return {"transmission_id": rid, "connector": connector, "operation": operation, "accepted": True,
                "payload_hash": ph, "decision_id": decision_id}

    def rows(self, limit=200):
        return self.store.all("SELECT * FROM outbox ORDER BY sent_at DESC LIMIT ?", (limit,))


class FabricStoreAdapter:
    """The Fabric's governed database. Only the Fabric's own principal can obtain the pooled
    handle; native() is denied to everyone (§03.4)."""

    def __init__(self, instance: dict, path: str):
        self.instance, self.path = instance, path
        self._conn = None
        self._lock = threading.RLock()

    def pooled(self):
        with self._lock:
            if self._conn is None:
                self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
                self._conn.row_factory = sqlite3.Row
            return self._conn, self._lock

    def invoke(self, operation, payload):
        raise PermissionError("The Fabric store is not invocable as a tool; use the Knowledge Fabric API")

    def raw(self):
        return self.pooled()[0]
