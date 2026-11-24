"""Data connections and the knowledge base (documents)."""
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, knowledge
from ..config import DATA_DIR, UPLOAD_LIMIT_MB
from ..datasources import KIND_IDS, KINDS, DataError, build_upload, introspect, run_query
from ..db import get_db
from ..deps import require
from ..models import Chunk, DataConnection, Document
from ..rbac import Access
from ..security import decrypt_bytes, decrypt_json, encrypt_bytes, encrypt_json
from ..sql_guard import GuardError

router = APIRouter(prefix="/api", tags=["data"])
MAX = UPLOAD_LIMIT_MB * 1024 * 1024


async def _read(f: UploadFile) -> bytes:
    data = await f.read(MAX + 1)
    if len(data) > MAX:
        raise HTTPException(413, f"{f.filename} is larger than {UPLOAD_LIMIT_MB} MB")
    return data


def conn_out(c: DataConnection) -> dict:
    snap = c.schema_snapshot or {}
    return {"id": c.id, "name": c.name, "kind": c.kind, "config": c.config, "status": c.status, "error": c.error,
            "has_secret": bool(c.secret_enc), "introspected_at": c.introspected_at, "allow_writes": bool((c.config or {}).get("allow_writes")),
            "tables": [{"name": t["name"], "rows": t.get("rows"), "columns": t.get("columns", [])} for t in snap.get("tables", [])],
            "endpoints": snap.get("endpoints", [])}


def _refresh(db: Session, c: DataConnection):
    try:
        c.schema_snapshot = introspect(c)
        c.status, c.error = "ready", ""
    except DataError as ex:
        c.status, c.error = "error", str(ex)
    c.introspected_at = datetime.now(timezone.utc)


# ------------------------------------------------------------------ data connections
@router.get("/data/kinds")
def kinds(a: Access = Depends(require("data:view"))):
    return KINDS


@router.get("/data/connections")
def list_conns(a: Access = Depends(require("data:view")), db: Session = Depends(get_db)):
    rows = db.execute(select(DataConnection).where(DataConnection.org_id == a.org_id).order_by(DataConnection.created_at)).scalars().all()
    return [conn_out(c) for c in rows]


class ConnIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str
    values: dict = {}


def _split(kind, values):
    spec = next(k for k in KINDS if k["id"] == kind)
    cfg, sec = {}, {}
    for f in spec["fields"]:
        v = values.get(f["name"]) or f.get("default")
        if v in (None, ""):
            if f.get("required"):
                raise HTTPException(400, f"{f['label']} is required")
            continue
        (sec if f.get("secret") else cfg)[f["name"]] = str(v).strip()
    return cfg, sec


@router.post("/data/connections")
def create_conn(body: ConnIn, a: Access = Depends(require("data:create")), db: Session = Depends(get_db)):
    if body.kind not in KIND_IDS or body.kind == "upload":
        raise HTTPException(400, "Unknown connection type (use the upload endpoint for files)")
    cfg, sec = _split(body.kind, body.values)
    c = DataConnection(org_id=a.org_id, name=body.name.strip(), kind=body.kind, config=cfg, secret_enc=encrypt_json(sec) if sec else None)
    db.add(c)
    db.flush()
    _refresh(db, c)
    audit.record(db, a.org_id, a.actor_label, "data.connected", c.name, {"kind": c.kind, "status": c.status}, commit=False)
    db.commit()
    return conn_out(c)


@router.post("/data/upload")
async def upload_conn(name: str = Form(""), file: UploadFile = File(...), a: Access = Depends(require("data:create")),
                      db: Session = Depends(get_db)):
    data = await _read(file)
    c = DataConnection(org_id=a.org_id, name=(name or file.filename).strip()[:200], kind="upload", config={"filename": file.filename})
    db.add(c)
    db.flush()
    try:
        build_upload(c, file.filename, data)
    except DataError as ex:
        db.rollback()
        raise HTTPException(400, str(ex)) from ex
    _refresh(db, c)
    audit.record(db, a.org_id, a.actor_label, "data.uploaded", c.name, {"file": file.filename, "status": c.status}, commit=False)
    db.commit()
    return conn_out(c)


@router.patch("/data/connections/{cid}")
def update_conn(cid: str, body: dict, a: Access = Depends(require("data:edit")), db: Session = Depends(get_db)):
    c = db.get(DataConnection, cid)
    if not c or c.org_id != a.org_id:
        raise HTTPException(404, "Connection not found")
    if body.get("name"):
        c.name = str(body["name"])[:200]
    if "allow_writes" in body and c.kind != "rest":
        c.config = {**c.config, "allow_writes": bool(body["allow_writes"])}
        audit.record(db, a.org_id, a.actor_label, "data.writes_enabled" if body["allow_writes"] else "data.writes_disabled", c.name, commit=False)
        if set(body) <= {"allow_writes"}:
            db.commit()
            return conn_out(c)
    if body.get("values") and c.kind != "upload":
        cfg, sec = _split(c.kind, {**c.config, **body["values"]})
        c.config = {**cfg, "allow_writes": bool(c.config.get("allow_writes"))}
        if sec:
            c.secret_enc = encrypt_json({**decrypt_json(c.secret_enc), **sec})
    _refresh(db, c)
    audit.record(db, a.org_id, a.actor_label, "data.updated", c.name, {"status": c.status}, commit=False)
    db.commit()
    return conn_out(c)


@router.post("/data/connections/{cid}/refresh")
def refresh(cid: str, a: Access = Depends(require("data:edit")), db: Session = Depends(get_db)):
    c = db.get(DataConnection, cid)
    if not c or c.org_id != a.org_id:
        raise HTTPException(404, "Connection not found")
    _refresh(db, c)
    db.commit()
    return conn_out(c)


@router.get("/data/connections/{cid}/tables/{table}")
def preview(cid: str, table: str, a: Access = Depends(require("data:view")), db: Session = Depends(get_db)):
    c = db.get(DataConnection, cid)
    if not c or c.org_id != a.org_id:
        raise HTTPException(404, "Connection not found")
    try:
        return run_query(c, f'SELECT * FROM "{table}"' if c.kind in ("postgres", "upload", "sqlite") else f"SELECT * FROM {table}",
                         a.allowed_tables(c.id), 50)
    except (GuardError, DataError) as ex:
        raise HTTPException(400, str(ex)) from ex


@router.delete("/data/connections/{cid}")
def delete_conn(cid: str, a: Access = Depends(require("data:delete")), db: Session = Depends(get_db)):
    c = db.get(DataConnection, cid)
    if not c or c.org_id != a.org_id:
        raise HTTPException(404, "Connection not found")
    db.delete(c)
    audit.record(db, a.org_id, a.actor_label, "data.deleted", c.name, commit=False)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ knowledge base
def _doc_path(d: Document):
    """The original file, encrypted at rest with the master key."""
    return DATA_DIR / "orgs" / d.org_id / "documents" / f"{d.id}.bin"


def doc_out(d: Document) -> dict:
    return {"id": d.id, "filename": d.filename, "size": d.size, "pages": d.pages, "chunks": d.chunks, "status": d.status,
            "error": d.error, "created_at": d.created_at, "has_file": _doc_path(d).exists()}


def _doc(db, a: Access, did: str) -> Document:
    d = db.get(Document, did)
    if not d or d.org_id != a.org_id:
        raise HTTPException(404, "Document not found")
    return d


# Only these are shown inside the browser; everything else is downloaded, so an uploaded file can never run as a web page.
_INLINE = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}


@router.get("/knowledge/documents/{did}/file")
def doc_file(did: str, download: bool = False, a: Access = Depends(require("knowledge:view")), db: Session = Depends(get_db)):
    d = _doc(db, a, did)
    p = _doc_path(d)
    if not p.exists():
        raise HTTPException(404, "The original file was not kept for this document (it was uploaded before downloads were available). Upload it again to download it.")
    data = decrypt_bytes(p.read_bytes())
    ext = Path(d.filename).suffix.lower()
    inline = not download and ext in _INLINE
    audit.record(db, a.org_id, a.actor_label, "knowledge.downloaded" if not inline else "knowledge.viewed", d.filename, {"document": d.id})
    name = quote(d.filename)
    return Response(data, media_type=_INLINE[ext] if inline else "application/octet-stream",
                    headers={"Content-Disposition": f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{name}",
                             "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@router.get("/knowledge/documents/{did}/text")
def doc_text(did: str, a: Access = Depends(require("knowledge:view")), db: Session = Depends(get_db)):
    """The text Aria XAI read from the document, page by page: what the agents actually search."""
    d = _doc(db, a, did)
    rows = db.execute(select(Chunk).where(Chunk.document_id == d.id).order_by(Chunk.ord)).scalars().all()
    pages: dict[int, list[str]] = {}
    for c in rows:
        pages.setdefault(c.page, []).append(c.text)
    return {"document": doc_out(d), "pages": [{"page": p, "text": "\n\n".join(t)} for p, t in sorted(pages.items())]}


@router.get("/knowledge/documents")
def docs(a: Access = Depends(require("knowledge:view")), db: Session = Depends(get_db)):
    rows = db.execute(select(Document).where(Document.org_id == a.org_id).order_by(Document.created_at.desc())).scalars().all()
    return [doc_out(d) for d in rows]


@router.post("/knowledge/upload")
async def upload_docs(files: list[UploadFile] = File(...), a: Access = Depends(require("knowledge:create")), db: Session = Depends(get_db)):
    out = []
    for f in files:
        data = await _read(f)
        h = hashlib.sha256(data).hexdigest()
        dup = db.execute(select(Document).where(Document.org_id == a.org_id, Document.sha256 == h)).scalar()
        if dup:
            if not _doc_path(dup).exists():  # uploaded before originals were kept: keep it now
                _doc_path(dup).parent.mkdir(parents=True, exist_ok=True)
                _doc_path(dup).write_bytes(encrypt_bytes(data))
            out.append({**doc_out(dup), "duplicate": True})
            continue
        d = Document(org_id=a.org_id, filename=f.filename or "document", mime=f.content_type or "", size=len(data), sha256=h, uploaded_by=a.actor_id)
        db.add(d)
        db.flush()
        p = _doc_path(d)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(encrypt_bytes(data))
        try:
            knowledge.ingest(db, d, data)
        except Exception as ex:  # noqa: BLE001
            d.status, d.error = "error", str(ex)[:500]
        audit.record(db, a.org_id, a.actor_label, "knowledge.uploaded", d.filename, {"status": d.status, "chunks": d.chunks}, commit=False)
        db.commit()
        out.append(doc_out(d))
    return out


@router.delete("/knowledge/documents/{did}")
def delete_doc(did: str, a: Access = Depends(require("knowledge:delete")), db: Session = Depends(get_db)):
    d = _doc(db, a, did)
    _doc_path(d).unlink(missing_ok=True)
    db.execute(Chunk.__table__.delete().where(Chunk.document_id == d.id))
    db.delete(d)
    audit.record(db, a.org_id, a.actor_label, "knowledge.deleted", d.filename, commit=False)
    db.commit()
    return {"ok": True}


@router.get("/knowledge/search")
def search(q: str, a: Access = Depends(require("knowledge:view")), db: Session = Depends(get_db)):
    return knowledge.search(db, a.org_id, q, 8)
