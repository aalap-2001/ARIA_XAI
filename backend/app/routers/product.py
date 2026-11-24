"""Understand my product → Blueprint review → publish."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit, studio, understanding
from ..llm.service import resolve
from .. import blueprint as BP
from ..db import get_db
from ..deps import require
from ..models import Blueprint, DataConnection, Document, LLMConnector, Membership, Organisation
from ..rbac import Access

router = APIRouter(prefix="/api", tags=["product"])


def bp_out(b: Blueprint, full=True) -> dict:
    d = {"id": b.id, "version": b.version, "status": b.status, "validation": b.validation, "progress": b.progress, "sources": b.sources,
         "error": b.error, "note": b.note, "created_at": b.created_at, "published_at": b.published_at,
         "industry": (b.content or {}).get("industry"), "summary": (b.content or {}).get("summary")}
    if full:
        d["content"] = b.content
        d["provenance"] = b.provenance or {}
    return d


def _get(db, a, bid) -> Blueprint:
    b = db.get(Blueprint, bid)
    if not b or b.org_id != a.org_id:
        raise HTTPException(404, "Blueprint not found")
    return b


@router.get("/setup")
def setup(a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    """The go-live checklist shown on Home."""
    c = lambda m, *w: db.execute(select(func.count()).select_from(m).where(m.org_id == a.org_id, *w)).scalar()  # noqa: E731
    org = db.get(Organisation, a.org_id)
    pub = db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id, Blueprint.status == "published")).scalar()
    latest = db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id).order_by(Blueprint.version.desc())).scalars().first()
    from ..models import ApiKey
    return {
        "ai_model": resolve(db, a.org_id)[0] is not None,
        "described": bool((org.product_description or "").strip()),
        "documents": c(Document), "connections": c(DataConnection),
        "blueprint": {"published": bp_out(pub, False) if pub else None, "latest": bp_out(latest, False) if latest else None},
        "members": c(Membership, Membership.status == "active"),
        "api_keys": c(ApiKey, ApiKey.revoked.is_(False)),
    }


@router.get("/product")
def get_product(a: Access = Depends(require("blueprint:view")), db: Session = Depends(get_db)):
    return {"description": db.get(Organisation, a.org_id).product_description}


@router.put("/product")
def put_product(body: dict, a: Access = Depends(require("blueprint:edit")), db: Session = Depends(get_db)):
    org = db.get(Organisation, a.org_id)
    org.product_description = str(body.get("description", ""))[:20000]
    audit.record(db, a.org_id, a.actor_label, "product.described", org.id, {"chars": len(org.product_description)})
    return {"description": org.product_description}


@router.post("/blueprints/generate")
def generate(body: dict | None = None, a: Access = Depends(require("blueprint:create")), db: Session = Depends(get_db)):
    if db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id, Blueprint.status == "generating")).scalar():
        raise HTTPException(409, "Aria XAI is already working on a blueprint for this organisation")
    b = understanding.start(db, a.org_id, a.actor_id, a.actor_label, note=(body or {}).get("note", "Understood from description, documents and data"))
    return bp_out(b)


@router.get("/blueprints")
def list_bps(a: Access = Depends(require("blueprint:view")), db: Session = Depends(get_db)):
    rows = db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id).order_by(Blueprint.version.desc())).scalars().all()
    return [bp_out(b, False) for b in rows]


@router.get("/blueprints/{bid}")
def get_bp(bid: str, a: Access = Depends(require("blueprint:view")), db: Session = Depends(get_db)):
    return bp_out(_get(db, a, bid))


class EditIn(BaseModel):
    content: dict


@router.put("/blueprints/{bid}")
def edit_bp(bid: str, body: EditIn, a: Access = Depends(require("blueprint:edit")), db: Session = Depends(get_db)):
    b = _get(db, a, bid)
    if b.status in ("generating",):
        raise HTTPException(409, "Wait for generation to finish")
    b = save_version(db, a, b, body.content)
    audit.record(db, a.org_id, a.actor_label, "blueprint.edited", b.id, {"version": b.version, "errors": len(b.validation["errors"])}, commit=False)
    db.commit()
    return bp_out(b)


def save_version(db, a: Access, b: Blueprint, content: dict, note: str = "", prov: dict | None = None) -> Blueprint:
    """Save edited content. A draft is updated in place; a published or archived version gets a new draft so history
    stays immutable. Each record's origin (Aria XAI or a person) is carried forward. The caller commits."""
    content = BP.normalise(content)
    result = BP.validate(content, understanding.connections_index(db, a.org_id), understanding.role_names(db, a.org_id))
    prov = prov if prov is not None else studio.provenance(b.content or {}, b.provenance, content, a.actor_label)
    if b.status != "draft":
        v = (db.execute(select(func.max(Blueprint.version)).where(Blueprint.org_id == a.org_id)).scalar() or 0) + 1
        note = note or f"Edited from v{b.version}"
        b = Blueprint(org_id=a.org_id, version=v, status="draft", content=content, validation=result, sources=b.sources, provenance=prov,
                      progress=[{"step": note, "state": "done"}], created_by=a.actor_id, note=note)
        db.add(b)
        db.flush()
    else:
        b.content, b.validation, b.provenance = content, result, prov
    return b


@router.post("/blueprints/{bid}/refine")
def refine(bid: str, body: dict, a: Access = Depends(require("blueprint:edit")), db: Session = Depends(get_db)):
    b = _get(db, a, bid)
    if not (body.get("instruction") or "").strip():
        raise HTTPException(400, "Tell Aria XAI what to change")
    if db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id, Blueprint.status == "generating")).scalar():
        raise HTTPException(409, "Aria XAI is already working on a blueprint")
    nb = understanding.start(db, a.org_id, a.actor_id, a.actor_label,
                             refine={"current": b.content, "instruction": body["instruction"], "section": body.get("section")},
                             note=f"Refined from v{b.version}: {body['instruction'][:200]}")
    return bp_out(nb)


@router.post("/blueprints/{bid}/publish")
def publish(bid: str, a: Access = Depends(require("blueprint:publish")), db: Session = Depends(get_db)):
    b = _get(db, a, bid)
    if b.status not in ("draft", "archived"):
        raise HTTPException(400, f"Only a draft or archived version can be published (this one is {b.status})")
    result = BP.validate(b.content, understanding.connections_index(db, a.org_id), understanding.role_names(db, a.org_id))
    b.validation = result
    if not result["ok"]:
        db.commit()
        raise HTTPException(400, {"message": "Fix the validation errors before publishing", "errors": result["errors"]})
    for other in db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id, Blueprint.status == "published")).scalars():
        other.status = "archived"
    b.status, b.published_by, b.published_at = "published", a.actor_id, datetime.now(timezone.utc)
    audit.record(db, a.org_id, a.actor_label, "blueprint.published", b.id, {"version": b.version}, commit=False)
    db.commit()
    return bp_out(b)


# ------------------------------------------------------------------ business rules via YAML
from fastapi.responses import Response  # noqa: E402


def _base(db, a: Access, base_id: str | None) -> Blueprint:
    if base_id:
        return _get(db, a, base_id)
    b = db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id, Blueprint.status == "published")).scalar() or \
        db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id, Blueprint.status.in_(["draft", "archived"]))
                   .order_by(Blueprint.version.desc())).scalars().first()
    if not b:
        raise HTTPException(400, "There is no blueprint yet. Use Understand my product first, then upload rule changes.")
    return b


def _merge(db, a: Access, base: Blueprint, text: str):
    sections, errors = BP.parse_rules_yaml(text)
    if errors:
        return None, {"ok": False, "stage": "file", "errors": errors, "warnings": []}
    merged = BP.normalise({**base.content, **sections})
    result = BP.validate(merged, understanding.connections_index(db, a.org_id), understanding.role_names(db, a.org_id))
    if not result["ok"]:
        return None, {"ok": False, "stage": "rules", "errors": result["errors"], "warnings": result["warnings"]}
    return merged, result


@router.get("/blueprints/{bid}/rules.yaml")
def download_rules(bid: str, a: Access = Depends(require("blueprint:view")), db: Session = Depends(get_db)):
    b = _get(db, a, bid)
    return Response(BP.rules_yaml(b.content, b.version), media_type="application/x-yaml",
                    headers={"Content-Disposition": f'attachment; filename="business-rules-v{b.version}.yaml"'})


class RulesIn(BaseModel):
    yaml: str
    base_id: str | None = None
    publish: bool = False


@router.post("/blueprints/rules/preview")
def preview_rules(body: RulesIn, a: Access = Depends(require("blueprint:edit")), db: Session = Depends(get_db)):
    """Check an uploaded rules file and show what would change. Nothing is saved."""
    base = _base(db, a, body.base_id)
    merged, result = _merge(db, a, base, body.yaml)
    if merged is None:
        return {**result, "base": {"id": base.id, "version": base.version, "status": base.status}, "changes": []}
    changes = BP.diff(base.content, merged, BP.RULE_SECTIONS)
    return {"ok": True, "errors": [], "warnings": result["warnings"], "changes": changes,
            "base": {"id": base.id, "version": base.version, "status": base.status}}


@router.post("/blueprints/rules/apply")
def apply_rules(body: RulesIn, a: Access = Depends(require("blueprint:edit")), db: Session = Depends(get_db)):
    """The user accepted the changes: save them as a new version (and make it live if asked and allowed)."""
    base = _base(db, a, body.base_id)
    merged, result = _merge(db, a, base, body.yaml)
    if merged is None:
        raise HTTPException(400, {"message": "The rules file was rejected", "errors": result["errors"]})
    changes = BP.diff(base.content, merged, BP.RULE_SECTIONS)
    if not changes:
        raise HTTPException(409, "This file makes no changes to the current rules")
    v = (db.execute(select(func.max(Blueprint.version)).where(Blueprint.org_id == a.org_id)).scalar() or 0) + 1
    nb = Blueprint(org_id=a.org_id, version=v, status="draft", content=merged, validation=result, sources=base.sources,
                   provenance=studio.provenance(base.content or {}, base.provenance, merged, a.actor_label),
                   progress=[{"step": f"Business rules uploaded as YAML, {len(changes)} change(s) from v{base.version}", "state": "done"}],
                   created_by=a.actor_id, note=f"Rules uploaded (YAML), {len(changes)} change(s) from v{base.version}")
    db.add(nb)
    db.flush()
    audit.record(db, a.org_id, a.actor_label, "blueprint.rules_uploaded", nb.id,
                 {"version": v, "from_version": base.version, "changes": [f"{c['change']} {c['label']} {c['id']}" for c in changes][:50]}, commit=False)
    if body.publish:
        if not a.can("blueprint:publish"):
            db.commit()
            raise HTTPException(403, f"Saved as draft v{v}. Your role cannot make it live; someone with publish permission can.")
        for other in db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id, Blueprint.status == "published")).scalars():
            other.status = "archived"
        nb.status, nb.published_by, nb.published_at = "published", a.actor_id, datetime.now(timezone.utc)
        audit.record(db, a.org_id, a.actor_label, "blueprint.published", nb.id, {"version": v}, commit=False)
    db.commit()
    return bp_out(nb) | {"changes": changes}


@router.get("/blueprints/compare/{from_id}/{to_id}")
def compare(from_id: str, to_id: str, a: Access = Depends(require("blueprint:view")), db: Session = Depends(get_db)):
    x, y = _get(db, a, from_id), _get(db, a, to_id)
    return {"from": {"id": x.id, "version": x.version, "status": x.status}, "to": {"id": y.id, "version": y.version, "status": y.status},
            "changes": BP.diff(x.content or {}, y.content or {})}
