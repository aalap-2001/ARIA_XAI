"""§06 / §07, the same engine, byte for byte, across domains. Only the bundle differs."""
import pytest

from ariax.core.bundle import BundleInvalid, load_dir, validate
from ariax.core.identity import Principal

EXPECTED = {
    ("healthcare", "victor"): {
        "88412": ("VALID", "SUBMIT_APPEAL", "ALLOW"),
        "88413": ("VALID", "SUBMIT_APPEAL", "REVIEW"),
        "88414": ("INVALID", "WRITE_OFF", "REVIEW"),
        "88415": ("INSUFFICIENT_EVIDENCE", "REQUEST_DOCS", "ALLOW"),
        "88416": ("INVALID", "WRITE_OFF", "ALLOW"),
    },
    ("finance", "uma"): {
        "A-1001": ("VALID", "APPROVE_LOAN", "ALLOW"),
        "A-1002": ("INVALID", "DECLINE_LOAN", "REVIEW"),
        "A-1003": ("INSUFFICIENT_EVIDENCE", "REQUEST_INFO", "ALLOW"),
        "A-1004": ("VALID", "APPROVE_LOAN", "REVIEW"),
        "A-1005": ("INVALID", "DECLINE_LOAN", "REVIEW"),
    },
    ("retail", "rex"): {
        "R-5001": ("VALID", "ISSUE_REFUND", "ALLOW"),
        "R-5002": ("INVALID", "DENY_REFUND", "ALLOW"),
        "R-5003": ("VALID", "ISSUE_REFUND", "REVIEW"),
        "R-5004": ("INVALID", "DENY_REFUND", "ALLOW"),
        "R-5005": ("INSUFFICIENT_EVIDENCE", "ESCALATE_TO_STORE", "ALLOW"),
    },
}


@pytest.mark.parametrize("domain,agent", list(EXPECTED))
def test_every_case_in_every_domain(platform, domain, agent):
    for case, (verdict, action, effect) in EXPECTED[(domain, agent)].items():
        r = platform.runner.run(domain, agent, case)
        assert r["status"] == "completed", r["error"]
        assert (r["verdict"], r["action"], r["effect"]) == (verdict, action, effect), case


def test_one_decision_id_joins_four_records(platform):
    r = platform.runner.run("healthcare", "victor", "88412")
    j = platform.decision_join(r["decision_id"])
    assert j["sentinel_audit"] and j["receipts"] and j["explanation"] and j["connector_audit"]
    assert any(c["decision_id"] == r["decision_id"] for c in j["connector_audit"])
    assert j["receipts"][0]["shown"][0]["subject"] == "Aetna:70553"


def test_review_then_execute(platform):
    r = platform.runner.run("finance", "uma", "A-1004")
    assert r["decision"]["status"] == "PENDING_REVIEW"
    out = platform.sentinel.review(r["decision_id"], True, "officer")
    assert out["status"] == "EXECUTED" and out["transmission"]["connector"] == "funding"
    assert platform.sentinel.watchdog()["incidents"] == []


def test_prompt_injection_is_flagged_not_obeyed(platform):
    r = platform.runner.run("healthcare", "victor", "88415")
    fetch = next(t for t in r["timeline"] if "denial letter" in t["title"])
    assert fetch["detail"]["injection_flags"]
    assert r["action"] == "REQUEST_DOCS"  # the letter said "approve immediately"; the rules decided


def test_pii_is_stripped_before_the_model(platform):
    r = platform.runner.run("finance", "uma", "A-1001")
    reason = next(t for t in r["timeline"] if t["subsystem"] == "sentinel" and "text" in (t["detail"] or {}))
    assert "512-44-9031" not in reason["detail"]["text"] and "Priya" not in reason["detail"]["text"]
    assert reason["detail"]["redactions_in"]


# ---------------------------------------------------------------- temporal: what was believed, when
def test_as_known_at_returns_the_old_belief(platform):
    p = Principal(tenant="st-marys-hospital", service="healthcare", agent="auditor")
    before = platform.fabric.query({"subject": "Aetna:70553"}, p, as_known_at="2024-07-14")
    after = platform.fabric.query({"subject": "Aetna:70553"}, p, as_known_at="2024-08-04")
    assert before[0]["value"]["requires_auth"] is False
    assert before[0]["source"]["source"] == "Aetna provider manual 2023"
    assert after[0]["value"]["requires_auth"] is True


def test_publication_lag_is_visible(platform):
    p = Principal(tenant="northwind-bank", service="finance", agent="auditor")
    ans = platform.fabric.query({"subject": "personal-loan"}, p)
    assert ans[0]["lag_days"] == 13.0  # published 20 Dec, ingested 2 Jan


def test_case_scope_hides_other_cases(platform):
    platform.runner.run("healthcare", "victor", "88412")
    platform.runner.run("healthcare", "victor", "88413")
    mine = platform.fabric.episodes(Principal(tenant="st-marys-hospital", service="healthcare", agent="victor", case="88412"))
    assert mine and all(e["case_id"] == "88412" for e in mine)


def test_reflection_proposes_and_gate_requires_evidence(platform):
    for _ in range(3):
        r = platform.runner.run("retail", "rex", "R-5001")
        platform.runner.record_outcome(r["run_id"], "customer_retained")
    props = platform.fabric.reflect(Principal(tenant="acme-retail", service="retail", agent="auditor"))
    assert props and props[0]["gate"] == "PROPOSED"
    out = platform.fabric.promote(props[0]["id"], "manager", True)
    assert out["status"] == "promoted"
    insight = platform.fabric.query({"entity": "Insight"}, Principal(tenant="acme-retail", service="retail", agent="auditor"))
    assert insight[0]["source"]["source"] == "reflection"


# ---------------------------------------------------------------- bundles: conformance & lifecycle
@pytest.mark.parametrize("name", ["healthcare", "finance", "retail"])
def test_shipped_bundles_validate_and_verify(platform, name):
    b = load_dir(platform.bundles_dir / name)
    assert validate(b) == []
    assert platform.bundles.verify(b) == []


def test_tampered_bundle_is_rejected(platform):
    b = load_dir(platform.bundles_dir / "healthcare")
    b["policies"]["statements"][1]["when"] = None  # quietly allow all appeals
    assert platform.bundles.verify(b)
    with pytest.raises(BundleInvalid):
        platform.bundles.import_signed(b, "attacker")


def test_new_domain_from_template_needs_no_engine_change(platform):
    platform.bundles.create_domain("insurance", "Insurance", "acme-insurance", "t", platform.bundles_dir / "_template")
    with pytest.raises(BundleInvalid):  # nobody pushes straight to production
        platform.bundles.transition("insurance", "1.0.0", "production", "t")
    for s in ["in_review", "approved", "staged", "production"]:
        platform.bundles.transition("insurance", "1.0.0", s, "t")
    r = platform.runner.run("insurance", "assistant", "W-1")
    assert (r["verdict"], r["effect"]) == ("VALID", "ALLOW")


def test_edit_creates_new_version_and_atomic_swap(platform):
    b = platform.bundles.active("retail")
    pol = dict(b["policies"])
    pol["statements"] = [dict(s, when={"all": [{"path": "amount", "op": "<=", "value": 2000}, {"path": "verdict", "op": "==", "value": "VALID"}]})
                         if s["id"] == "refund-up-to-500" else s for s in pol["statements"] if s["id"] != "refund-over-500"]
    d = platform.bundles.save_draft("retail", {"policies": pol}, "1.0.0", "t", "raise auto-refund limit")
    assert d["version"] == "1.0.1" and d["errors"] == []
    assert platform.runner.run("retail", "rex", "R-5003")["effect"] == "REVIEW"  # still old policy
    for s in ["in_review", "approved", "staged", "production"]:
        platform.bundles.transition("retail", "1.0.1", s, "t")
    assert platform.runner.run("retail", "rex", "R-5003")["effect"] == "ALLOW"  # new policy live
    assert platform.bundles.get("retail", "1.0.0")["status"] == "deprecated"
