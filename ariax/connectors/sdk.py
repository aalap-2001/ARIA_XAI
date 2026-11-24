"""Connectors, how the system reaches data and tools.

- No connection strings in application code: everything is resolved by logical name.
- Credentials are references (vault://...), resolved here, never handed to callers.
- ACL is enforced at resolve. Governed instances (governed_by: fabric) refuse every principal
  whose service is not the Fabric, and native() is denied on them (§03.4).
- Egress connectors refuse to send without a Sentinel decision_id that the ledger says is
  executable, "no external call happens without a verdict".
"""
import json
import os
from pathlib import Path

from ..core.errors import NotAuthorized, NotFound, NotPermitted
from ..core.identity import Principal
from ..core.ids import new_id, now_iso
from .adapters import EgressAdapter, FabricStoreAdapter, FixtureAdapter, Outbox, StreamAdapter

FIXTURE_TYPES = {"rest", "graphql", "jdbc", "erp", "crm", "pos", "core-banking", "fhir", "document-store"}


class SecretStore:
    """Resolves credentialRef → secret. Backed by env vars (ARIAX_SECRET_<NAME>) or data/secrets.json.
    Callers only ever learn whether a credential resolved, never its value."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._data = json.loads(self.path.read_text()) if self.path.exists() else {}

    def resolve(self, ref: str | None) -> bool:
        if not ref:
            return True
        env = "ARIAX_SECRET_" + ref.split("://")[-1].upper().replace("/", "_").replace("-", "_")
        return bool(os.environ.get(env) or self._data.get(ref) or ref.startswith("vault://"))  # dev vault accepts any ref


class Handle:
    def __init__(self, sdk, instance, adapter, principal: Principal, domain: str):
        self._sdk, self.instance, self._adapter, self.principal, self.domain = sdk, instance, adapter, principal, domain

    @property
    def name(self):
        return self.instance["name"]

    def invoke(self, operation: str, payload: dict | None = None, decision_id: str | None = None):
        payload = payload or {}
        if self.instance.get("egress"):
            if not decision_id:
                self._sdk.audit(self.principal, self.domain, self.name, "invoke:" + operation, "denied", None, "egress without decision_id")
                raise NotPermitted(f"'{self.name}' is an egress connector: a Sentinel decision_id is required")
            ok, why = self._sdk.decision_check(decision_id, self.domain, self.name, operation)
            if not ok:
                self._sdk.audit(self.principal, self.domain, self.name, "invoke:" + operation, "denied", decision_id, why)
                raise NotPermitted(f"decision {decision_id} does not authorise this send: {why}")
            result = self._adapter.invoke(operation, payload, decision_id=decision_id)
        else:
            result = self._adapter.invoke(operation, payload)
        self._sdk.audit(self.principal, self.domain, self.name, "invoke:" + operation, "ok", decision_id)
        return result

    def native(self):
        if self.instance.get("native_access") == "denied" or self.instance.get("governed_by"):
            self._sdk.audit(self.principal, self.domain, self.name, "native", "denied", None, "native access denied")
            raise NotPermitted(f"native() is denied on '{self.name}'")
        self._sdk.audit(self.principal, self.domain, self.name, "native", "ok", None)
        return self._adapter.raw()

    def pooled(self):
        """Fabric-internal: the pooled authenticated handle to a governed store."""
        if self.principal.service != "fabric" or not isinstance(self._adapter, FabricStoreAdapter):
            raise NotPermitted("pooled() is only available to the Fabric on its governed store")
        return self._adapter.pooled()


class ConnectorSDK:
    def __init__(self, store, secrets: SecretStore, fabric_db_path: str):
        self.store, self.secrets = store, secrets
        self.outbox = Outbox(store)
        self.fabric_db_path = fabric_db_path
        self._instances: dict[tuple[str, str], dict] = {}
        self._adapters: dict[tuple[str, str], object] = {}
        self._fixtures: dict[str, dict] = {}
        self.decision_check = lambda decision_id, domain, connector, op: (False, "no Sentinel attached")
        store.executescript("""
        CREATE TABLE IF NOT EXISTS connector_audit (id TEXT PRIMARY KEY, at TEXT, trace_id TEXT, decision_id TEXT,
            tenant TEXT, service TEXT, agent TEXT, domain TEXT, instance TEXT, instance_version TEXT,
            operation TEXT, outcome TEXT, reason TEXT);
        """)
        # Platform-level governed instance: the Fabric's store. Present in every deployment.
        self._register("_platform", {
            "name": "fabric-store", "type": "fabric-store", "system": "Knowledge Fabric store",
            "governed_by": "fabric", "native_access": "denied", "auth": {"credentialRef": "vault://platform/fabric-store"},
            "description": "The Fabric's governed database. Agents never receive a handle to it."}, {}, "platform")

    # -- registry
    def load_bundle(self, domain: str, bundle: dict):
        for k in [k for k in self._instances if k[0] == domain]:
            self._instances.pop(k)
            self._adapters.pop(k, None)
        fixtures = bundle.get("fixtures") or {}
        version = bundle["manifest"]["version"]
        for inst in (bundle.get("connectors") or {}).get("instances") or []:
            self._register(domain, inst, fixtures.get(inst["name"], {}), version)

    def _register(self, domain, inst, fixtures, version):
        inst = dict(inst)
        inst["_version"] = version
        t = inst.get("type")
        if t == "fabric-store" or inst.get("governed_by") == "fabric":
            adapter = FabricStoreAdapter(inst, self.fabric_db_path)
        elif inst.get("egress") or t == "egress":
            inst["egress"] = True
            adapter = EgressAdapter(inst, self.outbox)
        elif t == "kafka":
            adapter = StreamAdapter(inst, fixtures)
        else:
            adapter = FixtureAdapter(inst, fixtures)
        self._instances[(domain, inst["name"])] = inst
        self._adapters[(domain, inst["name"])] = adapter

    def instances(self, domain: str | None = None) -> list[dict]:
        out = []
        for (d, n), inst in self._instances.items():
            if domain and d not in (domain, "_platform"):
                continue
            out.append({"domain": d, "name": n, "type": inst.get("type"), "system": inst.get("system"),
                        "governed_by": inst.get("governed_by"), "native_access": inst.get("native_access", "allowed"),
                        "egress": bool(inst.get("egress")), "delegated": bool(inst.get("delegated")),
                        "credential_ref": (inst.get("auth") or {}).get("credentialRef"),
                        "credential_resolves": self.secrets.resolve((inst.get("auth") or {}).get("credentialRef")),
                        "acl": inst.get("acl") or {}, "operations": list((inst.get("operations") or {}).keys()),
                        "description": inst.get("description", ""), "version": inst.get("_version"),
                        "health": "ok"})
        return out

    # -- resolve
    def get(self, name: str, principal: Principal, domain: str | None = None) -> Handle:
        domain = domain or principal.service
        key = (domain, name) if (domain, name) in self._instances else ("_platform", name)
        inst = self._instances.get(key)
        if not inst:
            self.audit(principal, domain, name, "resolve", "denied", None, "unknown instance")
            raise NotFound(f"No connector instance '{name}' in domain '{domain}'")
        if inst.get("governed_by") and principal.service != inst["governed_by"]:
            self.audit(principal, domain, name, "resolve", "denied", None, f"governed_by {inst['governed_by']}")
            raise NotAuthorized(f"'{name}' is governed by the {inst['governed_by']}; principal service '{principal.service}' may not resolve it")
        acl = inst.get("acl") or {}
        if acl.get("agents") and principal.agent not in acl["agents"]:
            self.audit(principal, domain, name, "resolve", "denied", None, "ACL")
            raise NotAuthorized(f"agent '{principal.agent}' is not in the ACL for '{name}'")
        if inst.get("delegated") and not principal.on_behalf_of:
            self.audit(principal, domain, name, "resolve", "denied", None, "delegation required")
            raise NotAuthorized(f"'{name}' requires a delegated principal (on_behalf_of / consent token)")
        if not self.secrets.resolve((inst.get("auth") or {}).get("credentialRef")):
            self.audit(principal, domain, name, "resolve", "denied", None, "credential unresolved")
            raise NotAuthorized(f"credential for '{name}' could not be resolved")
        self.audit(principal, domain, name, "resolve", "ok", None)
        return Handle(self, inst, self._adapters[key], principal, domain)

    # -- connector.audit: which credential reached which system
    def audit(self, principal: Principal, domain, instance, operation, outcome, decision_id, reason=None):
        inst = self._instances.get((domain, instance)) or self._instances.get(("_platform", instance)) or {}
        self.store.execute("INSERT INTO connector_audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            new_id("ca"), now_iso(), principal.trace_id, decision_id, principal.tenant, principal.service,
            principal.agent, domain, instance, inst.get("_version"), operation, outcome, reason))

    def audit_rows(self, trace_id=None, decision_id=None, limit=300):
        if decision_id:
            return self.store.all("SELECT * FROM connector_audit WHERE decision_id=? ORDER BY at", (decision_id,))
        if trace_id:
            return self.store.all("SELECT * FROM connector_audit WHERE trace_id=? ORDER BY at", (trace_id,))
        return self.store.all("SELECT * FROM connector_audit ORDER BY at DESC LIMIT ?", (limit,))
