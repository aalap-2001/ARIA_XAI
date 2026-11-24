"""Uploaded documents can be read and downloaded by people allowed to view the knowledge base; originals are encrypted at rest."""
from app.config import DATA_DIR
from test_product import member

DOC = b"# Returns policy\n\nRefunds are allowed within 30 days of the order.\n"


def test_view_and_download_documents(signup):
    owner = signup()
    d = owner.post("/api/knowledge/upload", files=[("files", ("returns policy.md", DOC, "text/markdown"))]).json()[0]
    assert d["has_file"] is True

    # stored encrypted, never as plain text
    stored = (DATA_DIR / "orgs").rglob(f"{d['id']}.bin")
    raw = next(stored).read_bytes()
    assert b"Refunds are allowed" not in raw

    # download returns the exact original as an attachment
    r = owner.get(f"/api/knowledge/documents/{d['id']}/file?download=true")
    assert r.status_code == 200 and r.content == DOC
    assert r.headers["content-disposition"].startswith("attachment") and r.headers["content-type"] == "application/octet-stream"
    # non-PDF / non-image files are never shown inline, even without ?download
    assert owner.get(f"/api/knowledge/documents/{d['id']}/file").headers["content-disposition"].startswith("attachment")

    # the text the agents search, page by page
    t = owner.get(f"/api/knowledge/documents/{d['id']}/text").json()
    assert "Refunds are allowed" in t["pages"][0]["text"]

    kinds = [e["kind"] for e in owner.get("/api/audit").json()]
    assert "knowledge.downloaded" in kinds

    # a Builder can view; a role without knowledge access cannot; another organisation cannot
    builder = member(owner, "builder@example.com", "Builder")
    assert builder.get(f"/api/knowledge/documents/{d['id']}/file?download=true").content == DOC
    operator = member(owner, "operator@example.com", "Operator")
    assert operator.get(f"/api/knowledge/documents/{d['id']}/file").status_code == 403
    other = signup("Other Org Ltd")
    assert other.get(f"/api/knowledge/documents/{d['id']}/file").status_code == 404

    # deleting removes the stored original too
    owner.delete(f"/api/knowledge/documents/{d['id']}")
    assert not list((DATA_DIR / "orgs").rglob(f"{d['id']}.bin"))
