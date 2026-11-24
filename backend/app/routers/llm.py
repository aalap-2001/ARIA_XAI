"""Settings → AI models. Paste a key, load models, test, save, set default. Secrets never leave the server."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import require
from ..llm.base import LLMError
from ..llm.catalog import BY_ID, missing_required, provider, public_catalog, split_fields
from ..llm.service import resolve, run_test
from ..models import LLMConnector
from ..rbac import Access
from ..security import decrypt_json, encrypt_json, hint

router = APIRouter(prefix="/api/llm", tags=["llm"])


def out(c: LLMConnector) -> dict:
    p = BY_ID.get(c.provider, {})
    return {"id": c.id, "name": c.name, "provider": c.provider, "provider_name": p.get("name", c.provider), "group": p.get("group"),
            "config": c.config, "secret_hint": c.secret_hint, "model": c.model, "is_default": c.is_default, "status": c.status,
            "last_test": c.last_test, "created_at": c.created_at}


class Creds(BaseModel):
    provider: str
    values: dict = {}
    connector_id: str | None = None
    model: str | None = None


def _resolve(body: Creds, a: Access, db: Session):
    """Merge submitted values with a saved connector's secrets (blank secret fields keep the stored value)."""
    if body.provider not in BY_ID:
        raise HTTPException(400, f"Unknown provider '{body.provider}'")
    config, secrets = split_fields(body.provider, body.values)
    conn = None
    if body.connector_id:
        conn = db.get(LLMConnector, body.connector_id)
        if not conn or conn.org_id != a.org_id:
            raise HTTPException(404, "Connector not found")
        if conn.provider == body.provider:
            secrets = {**decrypt_json(conn.secret_enc), **secrets}
            config = {**conn.config, **config}
    miss = missing_required(body.provider, config, secrets)
    if miss:
        raise HTTPException(400, "Missing: " + ", ".join(miss))
    return config, secrets, conn


@router.get("/catalog")
def catalog(a: Access = Depends(require("llm:view"))):
    return public_catalog()


@router.get("/connectors")
def connectors(a: Access = Depends(require("llm:view")), db: Session = Depends(get_db)):
    rows = db.execute(select(LLMConnector).where(LLMConnector.org_id == a.org_id).order_by(LLMConnector.created_at)).scalars().all()
    return [out(c) for c in rows]


@router.get("/shared")
def shared(a: Access = Depends(require("llm:view")), db: Session = Depends(get_db)):
    """For businesses in a model-sharing group: which business's model they run on. Never includes secrets."""
    from ..models import Organisation
    org = db.get(Organisation, a.org_id)
    group = (org.settings or {}).get("model_group")
    if not group:
        return {"group": None}
    c, src = resolve(db, a.org_id)
    if c is None:
        return {"group": group, "source": None}
    if src is None:
        return {"group": group, "source": "self"}
    p = BY_ID.get(c.provider, {})
    return {"group": group, "source": {"business": src.name, "name": c.name, "provider_name": p.get("name", c.provider), "model": c.model, "status": c.status}}


@router.post("/models")
def load_models(body: Creds, a: Access = Depends(require("llm:view")), db: Session = Depends(get_db)):
    if not (a.can("llm:create") or a.can("llm:edit")):
        raise HTTPException(403, "Your role cannot configure AI models")
    config, secrets, _ = _resolve(body, a, db)
    try:
        models = provider(body.provider, config, secrets).list_models()
    except LLMError as ex:
        return {"ok": False, "error": str(ex), "models": []}
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": f"{type(ex).__name__}: {str(ex)[:300]}", "models": []}
    rec = BY_ID[body.provider].get("recommended_model")
    if rec in models:
        models = [rec] + [m for m in models if m != rec]
    return {"ok": True, "models": models, "recommended": rec if rec in models else None}


@router.post("/test")
def test(body: Creds, a: Access = Depends(require("llm:view")), db: Session = Depends(get_db)):
    if not (a.can("llm:create") or a.can("llm:edit")):
        raise HTTPException(403, "Your role cannot configure AI models")
    if not body.model:
        raise HTTPException(400, "Choose a model to test")
    config, secrets, conn = _resolve(body, a, db)
    result = run_test(provider(body.provider, config, secrets), body.model)
    if conn and conn.model == body.model:
        conn.status, conn.last_test = ("ok" if result["ok"] else "failed"), result
    audit.record(db, a.org_id, a.actor_label, "llm.tested", body.provider, {"model": body.model, "ok": result["ok"]})
    return result


class SaveIn(Creds):
    name: str = Field(min_length=1, max_length=200)
    test_result: dict | None = None
    make_default: bool = False


@router.post("/connectors")
def save(body: SaveIn, a: Access = Depends(require("llm:create")), db: Session = Depends(get_db)):
    if not body.model:
        raise HTTPException(400, "Choose a model before saving")
    config, secrets, _ = _resolve(Creds(provider=body.provider, values=body.values), a, db)
    first_secret = next((v for k, v in secrets.items() if k in ("api_key", "secret_access_key", "service_account_json")), "")
    c = LLMConnector(org_id=a.org_id, name=body.name.strip(), provider=body.provider, config=config,
                     secret_enc=encrypt_json(secrets) if secrets else None, secret_hint=hint(first_secret if isinstance(first_secret, str) else ""),
                     model=body.model, created_by=a.actor_id)
    if body.test_result and body.test_result.get("model") == body.model:
        c.status, c.last_test = ("ok" if body.test_result.get("ok") else "failed"), body.test_result
    has_default = db.execute(select(LLMConnector).where(LLMConnector.org_id == a.org_id, LLMConnector.is_default.is_(True))).scalar()
    db.add(c)
    db.flush()
    if body.make_default or not has_default:
        _set_default(db, a.org_id, c)
    audit.record(db, a.org_id, a.actor_label, "llm.created", c.name, {"provider": c.provider, "model": c.model, "default": c.is_default}, commit=False)
    db.commit()
    return out(c)


class PatchIn(BaseModel):
    name: str | None = None
    values: dict = {}
    model: str | None = None


@router.patch("/connectors/{cid}")
def update(cid: str, body: PatchIn, a: Access = Depends(require("llm:edit")), db: Session = Depends(get_db)):
    c = db.get(LLMConnector, cid)
    if not c or c.org_id != a.org_id:
        raise HTTPException(404, "Connector not found")
    config, secrets = split_fields(c.provider, body.values)
    if secrets:
        merged = {**decrypt_json(c.secret_enc), **secrets}
        c.secret_enc = encrypt_json(merged)
        first = next((v for k, v in secrets.items() if k in ("api_key", "secret_access_key", "service_account_json")), None)
        if isinstance(first, str):
            c.secret_hint = hint(first)
        c.status = "untested"
    if config:
        c.config = {**c.config, **config}
        c.status = "untested"
    if body.name:
        c.name = body.name.strip()[:200]
    if body.model and body.model != c.model:
        c.model, c.status = body.model, "untested"
    audit.record(db, a.org_id, a.actor_label, "llm.updated", c.name, {"model": c.model, "secret_changed": bool(secrets)}, commit=False)
    db.commit()
    return out(c)


def _set_default(db, org_id, c):
    for other in db.execute(select(LLMConnector).where(LLMConnector.org_id == org_id)).scalars():
        other.is_default = other.id == c.id


@router.post("/connectors/{cid}/default")
def make_default(cid: str, a: Access = Depends(require("llm:edit")), db: Session = Depends(get_db)):
    c = db.get(LLMConnector, cid)
    if not c or c.org_id != a.org_id:
        raise HTTPException(404, "Connector not found")
    _set_default(db, a.org_id, c)
    audit.record(db, a.org_id, a.actor_label, "llm.default_set", c.name, {"model": c.model}, commit=False)
    db.commit()
    return out(c)


@router.delete("/connectors/{cid}")
def delete(cid: str, a: Access = Depends(require("llm:delete")), db: Session = Depends(get_db)):
    c = db.get(LLMConnector, cid)
    if not c or c.org_id != a.org_id:
        raise HTTPException(404, "Connector not found")
    was_default = c.is_default
    db.delete(c)
    db.flush()
    if was_default:
        nxt = db.execute(select(LLMConnector).where(LLMConnector.org_id == a.org_id, LLMConnector.status == "ok")).scalar()
        if nxt:
            nxt.is_default = True
    audit.record(db, a.org_id, a.actor_label, "llm.deleted", c.name, commit=False)
    db.commit()
    return {"ok": True}
