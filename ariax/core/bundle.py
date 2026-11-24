"""§03.3 / §04, The domain bundle and the one Bundle Service.

A domain bundle is ONE signed, versioned artifact that configures all four subsystems.
It contains no executable logic. Onboarding a domain means writing one of these.

    bundles/<domain>/
        manifest.yaml     version, tenant, hash, signature
        ontology.yaml     what things are (entities, relationships)
        connectors.yaml   systems reached (POS, CRM, ERP, core banking, Kafka, Postgres...)
        fabric.yaml       roles (who sees what), decisions (what triggers a receipt), retention, seed facts
        rules.yaml        features, soft rules, thresholds (gate), hard rules
        policies.yaml     action cards (risk), Sentinel policy statements, model policy
        agents.yaml       agent cards (certification, limits) + playbooks (product logic)
        evaluator.yaml    what a good outcome is
        fixtures.yaml     demo data served by mock systems of record (dev only)

Lifecycle (every artifact, every domain):
    draft → in_review → approved → staged → canary → production → deprecated
Nobody pushes straight to production. Promotion to staged and beyond passes the sanity gate.
"""
import hashlib
import hmac
import os
import threading
from pathlib import Path

import yaml

from . import expr
from .errors import BundleInvalid, NotFound
from .ids import canonical, now_iso, sha256
from .store import Store, dumps, loads

ARTIFACTS = ["ontology", "connectors", "fabric", "rules", "policies", "agents", "evaluator", "fixtures"]
LIFECYCLE = ["draft", "in_review", "approved", "staged", "canary", "production", "deprecated"]
TRANSITIONS = {
    "draft": ["in_review"],
    "in_review": ["approved", "draft"],
    "approved": ["staged", "draft"],
    "staged": ["canary", "production", "draft"],
    "canary": ["production", "draft"],
    "production": ["deprecated"],
    "deprecated": [],
}
RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]
EFFECTS = ["ALLOW", "REVIEW", "BLOCK"]
VERDICTS = ["VALID", "INVALID", "INSUFFICIENT_EVIDENCE"]
STEP_KINDS = ["fetch", "recall", "reason", "evaluate", "act", "remember"]


# ----------------------------------------------------------------------------- signing
class Signer:
    """HMAC-SHA256 signing by the central authority. Production would use an asymmetric key
    held in an HSM so edge nodes can verify without being able to sign; the interface is the same."""

    def __init__(self, key_path: Path):
        env = os.environ.get("ARIAX_SIGNING_KEY")
        if env:
            self.key = env.encode()
        else:
            key_path.parent.mkdir(parents=True, exist_ok=True)
            if not key_path.exists():
                key_path.write_text(hashlib.sha256(os.urandom(32)).hexdigest())
            self.key = key_path.read_text().strip().encode()

    def sign(self, digest: str) -> str:
        return hmac.new(self.key, digest.encode(), hashlib.sha256).hexdigest()

    def verify(self, digest: str, signature: str | None) -> bool:
        return bool(signature) and hmac.compare_digest(self.sign(digest), signature)


def content_hash(artifacts: dict) -> str:
    return sha256(canonical({k: artifacts.get(k) for k in ARTIFACTS}))


# ----------------------------------------------------------------------------- disk I/O
def load_dir(path: Path) -> dict:
    path = Path(path)
    out = {"manifest": yaml.safe_load((path / "manifest.yaml").read_text(encoding="utf-8")) or {}}
    for name in ARTIFACTS:
        f = path / f"{name}.yaml"
        out[name] = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}
    return out


def write_dir(path: Path, bundle: dict):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    for name in ["manifest", *ARTIFACTS]:
        (path / f"{name}.yaml").write_text(yaml.safe_dump(bundle.get(name) or {}, sort_keys=False, allow_unicode=True), encoding="utf-8")


def to_yaml(obj) -> str:
    return yaml.safe_dump(obj or {}, sort_keys=False, allow_unicode=True)


def from_yaml(text: str, name: str):
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        raise BundleInvalid(f"{name}.yaml is not valid YAML", [str(e)])


# ----------------------------------------------------------------------------- validation
def validate(bundle: dict) -> list[str]:
    """Schema validation + cross-artifact consistency. Returns a list of errors (empty = valid).
    Cross-artifact checks only work because the artifacts arrive together as one bundle."""
    e: list[str] = []
    m = bundle.get("manifest") or {}
    for k in ("domain", "name", "version", "tenant"):
        if not m.get(k):
            e.append(f"manifest: '{k}' is required")

    onto = bundle.get("ontology") or {}
    entities = onto.get("entities") or {}
    if not entities:
        e.append("ontology: at least one entity is required")
    for r in onto.get("relationships") or []:
        for side in ("from", "to"):
            if r.get(side) not in entities:
                e.append(f"ontology.relationships[{r.get('name')}]: '{side}' entity '{r.get(side)}' is not defined")

    conns = {c.get("name"): c for c in (bundle.get("connectors") or {}).get("instances") or []}
    for name, c in conns.items():
        if not name:
            e.append("connectors: every instance needs a name")
        if not c.get("type"):
            e.append(f"connectors[{name}]: 'type' is required")
        if "connection_string" in c or "password" in str(c.get("auth", "")).lower():
            e.append(f"connectors[{name}]: credentials must be a credentialRef, never inline")
        if c.get("governed_by") == "fabric" and c.get("native_access") != "denied":
            e.append(f"connectors[{name}]: governed instances must declare native_access: denied")

    fabric = bundle.get("fabric") or {}
    roles = {r.get("agent"): r for r in fabric.get("roles") or []}
    for agent, r in roles.items():
        if r.get("scope") not in ("case", "tenant"):
            e.append(f"fabric.roles[{agent}]: scope must be 'case' or 'tenant'")
        for ent in r.get("entities") or []:
            if ent not in entities:
                e.append(f"fabric.roles[{agent}]: entity '{ent}' is not in the ontology")
    for i, f in enumerate(fabric.get("seed_facts") or []):
        if f.get("entity") not in entities:
            e.append(f"fabric.seed_facts[{i}]: entity '{f.get('entity')}' is not in the ontology")
        if not (f.get("source") or {}).get("source"):
            e.append(f"fabric.seed_facts[{i}]: provenance 'source.source' is required (no fact without a source)")
        for d in ("effective_from", "published_at", "ingested_at"):
            if not f.get(d):
                e.append(f"fabric.seed_facts[{i}]: '{d}' is required (four dates, not one)")

    rules = bundle.get("rules") or {}
    features = rules.get("features") or {}
    soft_outputs = set()
    for s in rules.get("soft") or []:
        soft_outputs.add(s.get("output"))
        for inp in s.get("inputs") or []:
            if inp.get("feature") not in features:
                e.append(f"rules.soft[{s.get('id')}]: feature '{inp.get('feature')}' is not declared")
    signals = set()
    for t in rules.get("thresholds") or []:
        signals.add(t.get("signal"))
        if t.get("from") not in soft_outputs:
            e.append(f"rules.thresholds[{t.get('signal')}]: soft output '{t.get('from')}' does not exist")
        if not (t.get("deny_below", 0) <= t.get("assert_above", 1)):
            e.append(f"rules.thresholds[{t.get('signal')}]: deny_below must be <= assert_above")
    for h in rules.get("hard") or []:
        if not h.get("id") or not h.get("require"):
            e.append("rules.hard: every rule needs an id and a 'require' condition")
            continue
        expr.validate_condition(h.get("require"), f"rules.hard[{h['id']}].require", e)
        if h.get("on_fail", "INVALID") not in VERDICTS:
            e.append(f"rules.hard[{h['id']}]: on_fail must be one of {VERDICTS}")
        for p in _paths(h.get("require")):
            root = p.split(".")[0]
            if root == "signals":
                if p.split(".")[1] not in signals:
                    e.append(f"rules.hard[{h['id']}]: signal '{p}' is not produced by any threshold")
            elif root not in features:
                e.append(f"rules.hard[{h['id']}]: '{p}' is not a declared feature (soft scores must pass the gate)")

    pol = bundle.get("policies") or {}
    actions = {a.get("name"): a for a in pol.get("actions") or []}
    for n, a in actions.items():
        if a.get("risk") not in RISK_LEVELS:
            e.append(f"policies.actions[{n}]: risk must be one of {RISK_LEVELS}")
        if a.get("connector") and a["connector"] not in conns:
            e.append(f"policies.actions[{n}]: connector '{a['connector']}' is not declared")
        elif a.get("connector") and not conns[a["connector"]].get("egress"):
            e.append(f"policies.actions[{n}]: connector '{a['connector']}' must be an egress connector")
    for s in pol.get("statements") or []:
        if s.get("effect") not in EFFECTS:
            e.append(f"policies.statements[{s.get('id')}]: effect must be one of {EFFECTS}")
        for a in s.get("actions") or []:
            if a != "*" and a not in actions:
                e.append(f"policies.statements[{s.get('id')}]: action '{a}' is not declared")
        expr.validate_condition(s.get("when"), f"policies.statements[{s.get('id')}].when", e)
    if pol.get("default", "BLOCK") != "BLOCK":
        e.append("policies: default must be BLOCK (default deny)")

    for a in (bundle.get("agents") or {}).get("agents") or []:
        aid = a.get("id")
        if not aid:
            e.append("agents: every agent needs an id")
            continue
        if aid not in roles:
            e.append(f"agents[{aid}]: no fabric role declared for this agent")
        for act in a.get("allowed_actions") or []:
            if act not in actions:
                e.append(f"agents[{aid}]: allowed action '{act}' is not declared in policies")
        src = a.get("case_source") or {}
        if src and src.get("connector") not in conns:
            e.append(f"agents[{aid}]: case_source connector '{src.get('connector')}' is not declared")
        for i, st in enumerate(a.get("playbook") or []):
            kind = st.get("step")
            if kind not in STEP_KINDS:
                e.append(f"agents[{aid}].playbook[{i}]: step must be one of {STEP_KINDS}")
            if kind == "fetch" and st.get("connector") not in conns:
                e.append(f"agents[{aid}].playbook[{i}]: connector '{st.get('connector')}' is not declared")
            if kind == "fetch" and conns.get(st.get("connector"), {}).get("governed_by"):
                e.append(f"agents[{aid}].playbook[{i}]: agents may not fetch from a governed instance")
            if kind in ("recall", "remember") and st.get("entity") not in entities:
                e.append(f"agents[{aid}].playbook[{i}]: entity '{st.get('entity')}' is not in the ontology")
            if kind == "act":
                for v, act in (st.get("by_verdict") or {}).items():
                    if v not in VERDICTS:
                        e.append(f"agents[{aid}].playbook[{i}]: unknown verdict '{v}'")
                    if act not in (a.get("allowed_actions") or []):
                        e.append(f"agents[{aid}].playbook[{i}]: action '{act}' is not in allowed_actions")
    for d in fabric.get("decisions") or []:
        if d not in actions:
            e.append(f"fabric.decisions: '{d}' is not a declared action")
    return e


def _paths(cond):
    if not cond:
        return []
    if "all" in cond or "any" in cond:
        return [p for c in cond.get("all", cond.get("any")) for p in _paths(c)]
    if "not" in cond:
        return _paths(cond["not"])
    return [cond["path"]] if "path" in cond else []


def bump(version: str) -> str:
    parts = (version or "1.0.0").split(".")
    while len(parts) < 3:
        parts.append("0")
    parts[2] = str(int(parts[2]) + 1)
    return ".".join(parts)


# ----------------------------------------------------------------------------- the service
class BundleService:
    """Central authority publishes versioned artifacts; edge nodes cache and evaluate locally;
    updates are atomic and verifiable offline. One bundle per domain per version."""

    def __init__(self, store: Store, signer: Signer, bundles_dir: Path):
        self.store, self.signer, self.bundles_dir = store, signer, Path(bundles_dir)
        self._active: dict[str, dict] = {}  # in-memory snapshot, swapped atomically
        self._swap = threading.Lock()
        self._listeners = []
        self.rejected: list[dict] = []
        store.executescript("""
        CREATE TABLE IF NOT EXISTS bundle_versions (
            domain TEXT, version TEXT, status TEXT, content TEXT, hash TEXT, signature TEXT,
            created_at TEXT, author TEXT, note TEXT, history TEXT,
            PRIMARY KEY (domain, version));
        """)

    # -- notifications
    def on_activate(self, fn):
        self._listeners.append(fn)

    def _activate(self, domain: str, bundle: dict):
        with self._swap:  # atomic: everything moves or nothing does
            snapshot = dict(self._active)
            snapshot[domain] = bundle
            self._active = snapshot
        for fn in self._listeners:
            fn(domain, bundle)

    # -- signing
    def seal(self, bundle: dict) -> dict:
        digest = content_hash(bundle)
        bundle["manifest"]["hash"] = digest
        bundle["manifest"]["signature"] = self.signer.sign(digest)
        return bundle

    def verify(self, bundle: dict) -> list[str]:
        m = bundle.get("manifest") or {}
        digest = content_hash(bundle)
        if m.get("hash") != digest:
            return [f"hash mismatch: manifest says {str(m.get('hash'))[:12]}…, content is {digest[:12]}… (bundle was modified after signing)"]
        if not self.signer.verify(digest, m.get("signature")):
            return ["signature does not verify against the platform signing key"]
        return []

    def sanity_gate(self, bundle: dict) -> list[str]:
        return self.verify(bundle) + validate(bundle)

    # -- boot
    def seed_from_disk(self):
        for d in sorted(p for p in self.bundles_dir.iterdir() if p.is_dir() and not p.name.startswith("_")):
            try:
                b = load_dir(d)
            except Exception as ex:  # noqa: BLE001
                self.rejected.append({"domain": d.name, "errors": [f"could not load: {ex}"]})
                continue
            domain = b["manifest"].get("domain", d.name)
            existing = self.store.one("SELECT version FROM bundle_versions WHERE domain=? AND version=?", (domain, b["manifest"].get("version")))
            if not existing:
                errs = self.sanity_gate(b)
                if errs:
                    self.rejected.append({"domain": domain, "errors": errs})
                    continue
                self._insert(b, "production", "disk-seed", "Imported from bundles/ on first boot")
        for row in self.store.all("SELECT domain, content FROM bundle_versions WHERE status='production'"):
            b = loads(row["content"])
            errs = self.sanity_gate(b)
            if errs:
                self.rejected.append({"domain": row["domain"], "errors": errs})
                continue
            self._activate(row["domain"], b)

    def _insert(self, b: dict, status: str, author: str, note: str):
        m = b["manifest"]
        hist = [{"status": status, "at": now_iso(), "by": author, "note": note}]
        self.store.execute(
            "INSERT INTO bundle_versions VALUES (?,?,?,?,?,?,?,?,?,?)",
            (m["domain"], m["version"], status, dumps(b), m.get("hash"), m.get("signature"), now_iso(), author, note, dumps(hist)))

    # -- reads
    def active(self, domain: str) -> dict:
        b = self._active.get(domain)
        if not b:
            raise NotFound(f"No production bundle for domain '{domain}'")
        return b

    def active_domains(self) -> dict[str, dict]:
        return dict(self._active)

    def versions(self, domain: str) -> list[dict]:
        rows = self.store.all("SELECT domain, version, status, hash, created_at, author, note, history FROM bundle_versions WHERE domain=? ORDER BY created_at DESC, version DESC", (domain,))
        for r in rows:
            r["history"] = loads(r["history"], [])
        return rows

    def get(self, domain: str, version: str) -> dict:
        r = self.store.one("SELECT * FROM bundle_versions WHERE domain=? AND version=?", (domain, version))
        if not r:
            raise NotFound(f"{domain}@{version} not found")
        return {"bundle": loads(r["content"]), "status": r["status"], "history": loads(r["history"], [])}

    def all_domains(self) -> list[str]:
        return [r["domain"] for r in self.store.all("SELECT DISTINCT domain FROM bundle_versions ORDER BY domain")]

    # -- writes
    def save_draft(self, domain: str, artifacts: dict, base_version: str | None, author: str, note: str = "") -> dict:
        base = self.get(domain, base_version)["bundle"] if base_version else (self._active.get(domain) or {"manifest": {}})
        b = {"manifest": dict(base.get("manifest") or {})}
        for name in ARTIFACTS:
            b[name] = artifacts.get(name, base.get(name) or {})
        if "manifest" in artifacts:
            for k, v in (artifacts["manifest"] or {}).items():
                if k not in ("hash", "signature", "version", "domain"):
                    b["manifest"][k] = v
        latest = self.store.one("SELECT version FROM bundle_versions WHERE domain=? ORDER BY created_at DESC, version DESC LIMIT 1", (domain,))
        b["manifest"]["domain"] = domain
        b["manifest"]["version"] = bump(latest["version"] if latest else "0.9.9")
        self.seal(b)
        errors = validate(b)
        self._insert(b, "draft", author, note or "Draft created in the console")
        return {"domain": domain, "version": b["manifest"]["version"], "errors": errors}

    def transition(self, domain: str, version: str, to: str, author: str, note: str = "") -> dict:
        cur = self.get(domain, version)
        frm = cur["status"]
        if to not in TRANSITIONS.get(frm, []):
            raise BundleInvalid(f"Cannot move {domain}@{version} from {frm} to {to}", {"allowed": TRANSITIONS.get(frm, [])})
        b = cur["bundle"]
        if LIFECYCLE.index(to) >= LIFECYCLE.index("approved") and to != "deprecated":
            errs = self.sanity_gate(b)
            if errs:
                raise BundleInvalid(f"Sanity gate rejected {domain}@{version}", errs)
        hist = cur["history"] + [{"status": to, "at": now_iso(), "by": author, "note": note}]
        if to == "production":
            for r in self.store.all("SELECT version, history FROM bundle_versions WHERE domain=? AND status='production'", (domain,)):
                h = loads(r["history"], []) + [{"status": "deprecated", "at": now_iso(), "by": author, "note": f"superseded by {version}"}]
                self.store.execute("UPDATE bundle_versions SET status='deprecated', history=? WHERE domain=? AND version=?", (dumps(h), domain, r["version"]))
        self.store.execute("UPDATE bundle_versions SET status=?, history=? WHERE domain=? AND version=?", (to, dumps(hist), domain, version))
        if to == "production":
            self._activate(domain, b)
        return {"domain": domain, "version": version, "status": to}

    def import_signed(self, bundle: dict, author: str) -> dict:
        """Air-gapped manual import: a signed bundle carried on media. Rejected before activation if bad."""
        errs = self.sanity_gate(bundle)
        if errs:
            raise BundleInvalid("Imported bundle rejected by the sanity gate", errs)
        m = bundle["manifest"]
        if self.store.one("SELECT 1 FROM bundle_versions WHERE domain=? AND version=?", (m["domain"], m["version"])):
            raise BundleInvalid(f"{m['domain']}@{m['version']} already exists")
        self._insert(bundle, "staged", author, "Imported signed bundle")
        return {"domain": m["domain"], "version": m["version"], "status": "staged"}

    def create_domain(self, domain: str, name: str, tenant: str, author: str, template_dir: Path) -> dict:
        if self.store.one("SELECT 1 FROM bundle_versions WHERE domain=?", (domain,)):
            raise BundleInvalid(f"Domain '{domain}' already exists")
        b = load_dir(template_dir)
        b["manifest"].update({"domain": domain, "name": name, "tenant": tenant, "version": "1.0.0"})
        text = canonical(b).replace("__DOMAIN__", domain)
        import json
        b = json.loads(text)
        self.seal(b)
        self._insert(b, "draft", author, "Created from template")
        return {"domain": domain, "version": "1.0.0", "errors": validate(b)}
