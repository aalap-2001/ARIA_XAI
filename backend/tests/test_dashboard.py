"""The Command Centre is built for the person who is signed in: their approvals, their team's work, their role's view."""
from test_product import chat, member, setup_product


def test_dashboard_for_owner_and_operator(signup):
    cl = signup("Dash Rentals")
    setup_product(cl)
    chat(cl, "How many orders do we have?")
    d = cl.get("/api/dashboard")
    assert d.status_code == 200, d.text
    x = d.json()
    assert set(x["kpis"]) >= {"attention", "in_progress", "completed", "exceptions", "auto_rate", "team"}
    assert len(x["series"]) == 30 and sum(s["requests"] for s in x["series"]) >= 1
    assert x["team"][0]["name"] == "Aria Orchestrator" and x["team"][0]["work"] >= 1
    assert x["usage"] is not None and x["persona"]["name"] == "Aria"
    assert any(f["state"] == "answered" for f in x["feed"])

    # an Operator sees the dashboard, but not org-wide usage or the owner's conversations by title
    op = member(cl, "op.dash@example.com", "Operator")
    o = op.get("/api/dashboard").json()
    assert o["usage"] is None and o["sees"]["all"] is False
    assert all(f["text"] == "Answered a colleague's request" for f in o["feed"] if f["state"] == "answered")
