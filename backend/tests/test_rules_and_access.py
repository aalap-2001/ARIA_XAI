"""Business rules via YAML, version switching, Executor limits by role, history by user, Aria Watch access."""
import yaml
from conftest import Client
from test_product import chat, member, plan_from, setup_product


def rules_of(cl, bp_id):
    r = cl.get(f"/api/blueprints/{bp_id}/rules.yaml")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    return yaml.safe_load(r.text)


def test_nonsense_files_are_rejected_with_clear_errors(signup):
    cl = signup()
    setup_product(cl)
    cases = {
        "": "empty",
        "this: [is: not: yaml": "not valid YAML",
        "- just\n- a\n- list\n": "does not contain Aria XAI business rules",
        "recipe: pancakes\ningredients: [eggs, flour]\n": "none of the sections",
        "rules: hello\n": "must be a list",
        "rules:\n  - description: no id or condition\n": "missing: id, condition",
        "rules:\n  - id: r1\n    condition: {path: ghost_fact, op: '<', value: 1}\n": "fact 'ghost_fact' is not defined",
    }
    for text, why in cases.items():
        p = cl.post("/api/blueprints/rules/preview", json={"yaml": text}).json()
        assert p["ok"] is False and any(why in e for e in p["errors"]), (text, p["errors"])
        assert cl.post("/api/blueprints/rules/apply", json={"yaml": text}).status_code == 400


def test_upload_shows_changes_then_creates_a_version_and_switching_works(signup):
    cl = signup()
    bp = setup_product(cl)
    doc = rules_of(cl, bp["id"])
    assert cl.post("/api/blueprints/rules/apply", json={"yaml": yaml.safe_dump(doc)}).status_code == 409  # unchanged file
    doc["rules"][0]["condition"]["value"] = 14                       # tighten the refund window
    doc["rules"].append({"id": "refund_cap", "description": "No refund above 2000", "citation": "policy.md p.1",
                         "applies_to": ["ISSUE_REFUND"], "condition": {"path": "refund_amount", "op": "<=", "value": 2000}})
    doc["rules"] = [r for r in doc["rules"] if r["id"] != "no_damage"]
    text = yaml.safe_dump(doc)
    p = cl.post("/api/blueprints/rules/preview", json={"yaml": text}).json()
    assert p["ok"] and p["base"]["version"] == bp["version"]
    got = {(c["change"], c["id"]) for c in p["changes"]}
    assert got == {("added", "refund_cap"), ("removed", "no_damage"), ("changed", "refund_window")}
    assert len(cl.get("/api/blueprints").json()) == 1  # preview saved nothing
    nb = cl.post("/api/blueprints/rules/apply", json={"yaml": text, "publish": True}).json()
    assert nb["status"] == "published" and nb["version"] == bp["version"] + 1
    versions = {v["version"]: v for v in cl.get("/api/blueprints").json()}
    assert versions[bp["version"]]["status"] == "archived"
    cmp = cl.get(f"/api/blueprints/compare/{bp['id']}/{nb['id']}").json()
    assert {c["id"] for c in cmp["changes"]} >= {"refund_cap", "no_damage", "refund_window"}
    assert cl.post(f"/api/blueprints/{bp['id']}/publish").json()["status"] == "published"  # switch back to the earlier version
    assert {v["version"]: v["status"] for v in cl.get("/api/blueprints").json()}[nb["version"]] == "archived"


def test_executor_is_limited_to_the_roles_permitted_actions(signup):
    owner = signup()
    setup_product(owner)
    r = owner.post("/api/roles", json={"name": "Support lead", "permissions": ["chat:use", "approvals:view", "approvals:approve"],
                                       "scopes": {"agents": ["*"], "data": {"*": ["*"]}, "actions": ["MARK_REFUNDED"], "approval_limit": 5000}}).json()
    tok = owner.post("/api/users/invite", json={"email": "lead@example.com", "role_id": r["id"]}).json()["invite_url"].rsplit("/", 1)[1]
    lead = Client()
    lead.post(f"/api/invites/{tok}/accept", json={"name": "Lead", "password": "Str0ngPassword!"})
    lead.refresh()
    ev = chat(lead, "Refund order 1001")  # ISSUE_REFUND is outside this role: the Executor may not even propose it
    assert not [e for e in ev if e.get("type") == "plan"]
    # a role without Aria Executor cannot run plans at all
    no_exec = owner.post("/api/roles", json={"name": "Readers", "permissions": ["chat:use"], "scopes": {"agents": ["orchestrator", "analyst"],
                                                                                                       "data": {"*": ["*"]}, "actions": ["*"], "approval_limit": None}}).json()
    m = next(x for x in owner.get("/api/users").json()["members"] if x["email"] == "lead@example.com")
    owner.patch(f"/api/users/{m['id']}", json={"role_id": no_exec["id"]})
    assert [g["id"] for g in lead.get("/api/team").json()["leads"]] == ["analyst"]


def test_history_is_per_user_and_auditors_see_everyone(signup):
    owner = signup()
    setup_product(owner)
    op = member(owner, "hist-op@example.com", "Operator")
    chat(op, "Refund order 1001")
    chat(owner, "Refund order 1003")
    mine = op.get("/api/history").json()
    assert mine["can_see_everyone"] is False and len(mine["conversations"]) == 1
    all_ = owner.get("/api/history").json()
    assert all_["can_see_everyone"] and len(all_["conversations"]) == 2
    op_id = next(u["id"] for u in all_["users"] if u["email"] == "hist-op@example.com")
    only_op = owner.get(f"/api/history?user_id={op_id}").json()["conversations"]
    assert [c["user"]["email"] for c in only_op] == ["hist-op@example.com"]
    conv = owner.get(f"/api/history/{only_op[0]['id']}").json()
    assert conv["messages"] and conv["plans"]
    owners_conv = next(c for c in all_["conversations"] if c["user"]["email"] == owner.email)
    assert op.get(f"/api/history/{owners_conv['id']}").status_code == 404  # operators cannot read other people's history


def test_aria_watch_requires_the_watch_agent_in_the_role(signup):
    owner = signup()
    setup_product(owner)
    cat = owner.get("/api/roles/catalog").json()
    assert [t["id"] for t in cat["team"]] == ["orchestrator", "analyst", "executor", "watch"]
    r = owner.post("/api/roles", json={"name": "No watch", "permissions": ["chat:use", "approvals:view"],
                                       "scopes": {"agents": ["orchestrator", "analyst"], "data": {}, "actions": [], "approval_limit": 0}}).json()
    tok = owner.post("/api/users/invite", json={"email": "nw@example.com", "role_id": r["id"]}).json()["invite_url"].rsplit("/", 1)[1]
    u = Client()
    u.post(f"/api/invites/{tok}/accept", json={"name": "NW", "password": "Str0ngPassword!"})
    u.refresh()
    assert u.get("/api/suggestions").status_code == 403 and u.get("/api/events").status_code == 403
