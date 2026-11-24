"""§08, each enforcement layer ships with a test that proves it. These run against a real platform."""
import sqlite3

import pytest

from ariax.core.errors import GateViolation, KillSwitchEngaged, NotAuthorized, NotPermitted
from ariax.core.identity import Principal, fabric_principal
from ariax.rules.engine import GatedSignals, HardEngine


def product(p, domain="healthcare", agent="victor", case="88412", **kw):
    t = p.bundles.active(domain)["manifest"]["tenant"]
    return Principal(tenant=t, service=domain, agent=agent, case=case, **kw)


# 1. Fabric bypass returns nothing
def test_fabric_bypass_returns_nothing(platform):
    platform.runner.run("healthcare", "victor", "88412")
    raw = sqlite3.connect(str(platform.data_dir / "fabric.db"))
    assert raw.execute("SELECT * FROM facts").fetchall() == []
    assert raw.execute("SELECT * FROM episodes").fetchall() == []
    assert raw.execute("SELECT * FROM receipts").fetchall() == []


def test_legitimate_query_returns_exactly_the_scoped_rows(platform):
    ans = platform.fabric.query({"entity": "PayerRule", "subject": "Aetna:70553"}, product(platform))
    assert len(ans) == 1 and ans[0]["value"]["requires_auth"] is True
    assert ans[0]["source"]["source"] == "Aetna bulletin AET-2024-11"


# 2. Governed connector refuses a product principal
def test_governed_connector_refuses_product_principal(platform):
    with pytest.raises(NotAuthorized):
        platform.connectors.get("facts-db", product(platform))
    with pytest.raises(NotAuthorized):
        platform.connectors.get("fabric-store", product(platform), domain="_platform")


# 3. native() denied on a governed instance, even for the Fabric itself
def test_native_denied_on_governed_instance(platform):
    fp = fabric_principal("st-marys-hospital")
    with pytest.raises(NotPermitted):
        platform.connectors.get("fabric-store", fp, domain="_platform").native()


# 4. No soft output reaches hard without the gate
def test_no_path_from_soft_to_hard_without_gate():
    with pytest.raises(GateViolation):
        HardEngine().validate([], {}, {"strong_grounds": True})
    with pytest.raises(GateViolation):
        GatedSignals({"strong_grounds": True}, [])


def test_bundle_validation_rejects_hard_rule_reading_soft_score(platform):
    from ariax.core.bundle import validate
    b = dict(platform.bundles.active("healthcare"))
    b["rules"] = dict(b["rules"], hard=b["rules"]["hard"] + [{"id": "sneaky", "require": {"path": "appeal_strength", "op": ">", "value": 0.5}}])
    assert any("must pass the gate" in e for e in validate(b))


# 5. External call without a verdict is refused, and anything that slips through is flagged
def test_egress_without_decision_is_refused(platform):
    h = platform.connectors.get("clearinghouse", product(platform))
    with pytest.raises(NotPermitted):
        h.invoke("submit_appeal", {"x": 1})
    with pytest.raises(NotPermitted):
        h.invoke("submit_appeal", {"x": 1}, decision_id="dc_forged")


def test_decision_id_is_single_use(platform):
    r = platform.runner.run("healthcare", "victor", "88412")
    assert r["effect"] == "ALLOW"
    h = platform.connectors.get("clearinghouse", product(platform))
    with pytest.raises(NotPermitted):  # already EXECUTED, cannot be replayed
        h.invoke("submit_appeal", {"replay": True}, decision_id=r["decision_id"])


def test_watchdog_reconciles(platform):
    platform.runner.run("healthcare", "victor", "88412")
    assert platform.sentinel.watchdog()["incidents"] == []
    platform.connectors.outbox.record("clearinghouse", "raw_send", {"x": 1}, None, via="raw-bypass")
    assert len(platform.sentinel.watchdog()["incidents"]) == 1


# 6. CI lint, no domain nouns in the engine
def test_engine_has_no_domain_vocabulary():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from leak_check import scan
    assert scan() == []


# Tamper evidence and kill switch
def test_audit_chain_detects_tampering(platform):
    platform.runner.run("healthcare", "victor", "88412")
    assert platform.sentinel.ledger.verify()["ok"]
    platform.store.execute("UPDATE sentinel_audit SET effect='ALLOW' WHERE kind='decision'")
    platform.store.execute("UPDATE sentinel_audit SET detail='{}' WHERE seq=1")
    assert not platform.sentinel.ledger.verify()["ok"]


def test_kill_switch_blocks_agent(platform):
    platform.sentinel.set_kill_switch("agent:healthcare:victor", True, "test")
    r = platform.runner.run("healthcare", "victor", "88412")
    assert r["status"] == "failed" and "KILL_SWITCH" in r["error"]
    with pytest.raises(KillSwitchEngaged):
        platform.chat.reply("healthcare", "victor", "run 88412")


def test_episodes_are_append_only(platform):
    platform.runner.run("healthcare", "victor", "88412")
    with pytest.raises(sqlite3.IntegrityError):
        platform.fabric.conn.execute("UPDATE _episodes SET outcome='edited'")


def test_delegated_connector_requires_consent(platform):
    with pytest.raises(NotAuthorized):
        platform.connectors.get("bureau-api", product(platform, "finance", "uma", "A-1001"))
    assert platform.connectors.get("bureau-api", product(platform, "finance", "uma", "A-1001", on_behalf_of="consent-123"))
