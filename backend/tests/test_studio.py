"""Aria XAI Studio: six layers, add / edit / delete records with provenance, settings, reset to original, role access, audit."""
from test_product import member, setup_product


def kinds(cl):
    return [e["kind"] for e in cl.get("/api/audit").json()]


def test_layers_records_provenance_and_reset(signup):
    cl = signup()
    bp = setup_product(cl)
    st = cl.get("/api/studio").json()
    assert [x["name"] for x in st["layers"]] == ["Cognitive Core", "Motivation Engine", "Knowledge Fabric", "Swarm Orchestrator",
                                                 "Anthropomorphic Interface", "Governance Sentinel"]
    assert st["original"]["id"] == bp["id"]

    # add a fact: new draft version, marked as made by a person; generated records stay "system"
    r = cl.post("/api/studio/records", json={"blueprint_id": bp["id"], "section": "facts", "op": "add",
                                              "record": {"name": "customer_tier", "type": "string", "description": "Tier of the customer"}})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["version"] == bp["version"] + 1 and d["status"] == "draft"
    assert d["provenance"]["facts"]["customer_tier"]["kind"] == "human" and d["provenance"]["facts"]["customer_tier"]["change"] == "added"
    first = bp["content"]["facts"][0]["name"]
    assert first not in d["provenance"].get("facts", {})

    # duplicate names are refused
    dup = cl.post("/api/studio/records", json={"blueprint_id": d["id"], "section": "facts", "op": "add",
                                                "record": {"name": "customer_tier", "type": "string", "description": "x"}})
    assert dup.status_code == 409

    # edit a generated record: it becomes the person's; delete one
    rec = {**bp["content"]["facts"][0], "description": "Changed by a person"}
    d = cl.post("/api/studio/records", json={"blueprint_id": d["id"], "section": "facts", "op": "edit", "key": first, "record": rec}).json()
    assert d["provenance"]["facts"][first]["change"] == "edited"
    d = cl.post("/api/studio/records", json={"blueprint_id": d["id"], "section": "starter_questions", "op": "add", "record": "What changed today?"}).json()
    assert "What changed today?" in d["content"]["starter_questions"]
    d = cl.post("/api/studio/records", json={"blueprint_id": d["id"], "section": "starter_questions", "op": "delete", "key": "What changed today?"}).json()
    assert "What changed today?" not in d["content"]["starter_questions"]

    # settings: validated, saved, audited
    bad = cl.put("/api/studio/swarm/settings", json={"settings": {"agent_steps": 999}})
    assert bad.status_code == 400
    assert cl.put("/api/studio/swarm/settings", json={"settings": {"agent_steps": 6}}).json()["agent_steps"] == 6

    # reset preview lists the changes; confirm restores the original records and default settings
    pv = cl.post("/api/studio/cognitive/reset", json={"blueprint_id": d["id"]}).json()
    assert {c["id"] for c in pv["changes"]} >= {"customer_tier", first}
    done = cl.post("/api/studio/cognitive/reset", json={"blueprint_id": d["id"], "confirm": True}).json()
    assert done["blueprint"]["content"]["facts"] == bp["content"]["facts"]
    assert not done["blueprint"]["provenance"].get("facts")
    cl.post("/api/studio/swarm/reset", json={"blueprint_id": done["blueprint"]["id"], "confirm": True})
    assert next(x for x in cl.get("/api/studio").json()["layers"] if x["id"] == "swarm")["settings"]["agent_steps"] == 10
    # a reset of the original itself is the original, so "Reset" never counts as the original
    assert cl.get("/api/studio").json()["original"]["id"] == bp["id"]

    k = kinds(cl)
    for x in ("studio.record_added", "studio.record_edited", "studio.record_deleted", "studio.settings_changed", "studio.layer_reset"):
        assert x in k, x


def test_try_the_engine_changes_nothing(signup):
    cl = signup()
    bp = setup_product(cl)
    act = bp["content"]["actions"][0]["name"]
    n = len(cl.get("/api/audit").json())
    r = cl.post("/api/studio/engine/try", json={"blueprint_id": bp["id"], "action": act, "facts": {}})
    assert r.status_code == 200, r.text
    assert r.json()["verdict"] in ("VALID", "INVALID", "INSUFFICIENT_EVIDENCE") and "authority" in r.json()
    assert len(cl.get("/api/audit").json()) == n and cl.get("/api/decisions").json() == []


def test_studio_access_follows_roles(signup):
    owner = signup()
    bp = setup_product(owner)
    builder, reviewer = member(owner, "b@example.com", "Builder"), member(owner, "r@example.com", "Reviewer")
    layers = {x["id"]: x for x in builder.get("/api/studio").json()["layers"]}
    assert layers["cognitive"]["can_edit_records"] and layers["swarm"]["can_edit_settings"]
    assert not layers["governance"]["can_edit_settings"]  # guardrails are organisation policy
    assert builder.put("/api/studio/governance/settings", json={"settings": {"redact_contact_data": False}}).status_code == 403
    assert owner.put("/api/studio/governance/settings", json={"settings": {"redact_contact_data": False}}).status_code == 200
    # reviewers can see everything but change nothing
    assert reviewer.get("/api/studio").status_code == 200
    assert reviewer.post("/api/studio/records", json={"blueprint_id": bp["id"], "section": "facts", "op": "add",
                                                      "record": {"name": "x", "type": "string", "description": "x"}}).status_code == 403
    assert reviewer.post("/api/studio/cognitive/reset", json={"blueprint_id": bp["id"], "confirm": True}).status_code == 403
