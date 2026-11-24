"""Aria XAI Studio API: the six framework layers. Every add, edit, delete, settings change and reset is audited."""
import copy

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import audit, studio
from ..db import get_db
from ..deps import current, require
from ..models import Organisation
from ..rbac import Access
from .product import _get, bp_out, save_version

router = APIRouter(prefix="/api/studio", tags=["studio"])


def _layer(layer_id: str) -> dict:
    if layer_id not in studio.BY_ID:
        raise HTTPException(404, "Unknown layer")
    return studio.BY_ID[layer_id]


def _need(a: Access, perm: str):
    if not a.can(perm):
        raise HTTPException(403, "Your role cannot change this. Ask an Owner or Org admin.")


@router.get("")
def overview(a: Access = Depends(require("blueprint:view")), db: Session = Depends(get_db)):
    org = db.get(Organisation, a.org_id)
    orig = studio.original(db, a.org_id)
    return {
        "layers": [{"id": x["id"], "number": i + 1, "name": x["name"], "runs_on": x["runs_on"], "purpose": x["purpose"],
                    "sections": x["sections"], "settings_spec": x["settings"], "settings": studio.get(org, x["id"]),
                    "defaults": studio.defaults(x["id"]), "can_edit_settings": a.can(studio.edit_permission(x["id"])),
                    "can_edit_records": a.can("blueprint:edit") and not x.get("readonly"), "readonly": bool(x.get("readonly"))} for i, x in enumerate(studio.LAYERS)],
        "original": {"id": orig.id, "version": orig.version} if orig else None,
    }


class SettingsIn(BaseModel):
    settings: dict


@router.put("/{layer_id}/settings")
def put_settings(layer_id: str, body: SettingsIn, a: Access = Depends(current), db: Session = Depends(get_db)):
    L = _layer(layer_id)
    _need(a, studio.edit_permission(layer_id))
    values, errors = studio.clean(layer_id, body.settings)
    if errors:
        raise HTTPException(400, {"message": "Some settings are not valid", "errors": errors})
    org = db.get(Organisation, a.org_id)
    before = studio.get(org, layer_id)
    after = studio.save(org, layer_id, values)
    changed = {k: {"before": before.get(k), "after": after[k]} for k in after if before.get(k) != after[k]}
    audit.record(db, a.org_id, a.actor_label, "studio.settings_changed", layer_id, {"layer": L["name"], "changes": changed}, commit=False)
    db.commit()
    return after


class RecordIn(BaseModel):
    blueprint_id: str
    section: str
    op: str  # add | edit | delete
    key: str | None = None
    record: dict | str | None = None


@router.post("/records")
def change_record(body: RecordIn, a: Access = Depends(require("blueprint:edit")), db: Session = Depends(get_db)):
    if body.section not in studio.RECORD_SECTIONS or body.op not in ("add", "edit", "delete"):
        raise HTTPException(400, "Unknown section or operation")
    b = _get(db, a, body.blueprint_id)
    if b.status in ("generating", "failed"):
        raise HTTPException(409, "This version cannot be edited")
    content = copy.deepcopy(b.content or {})
    items = list(content.get(body.section) or [])
    s, plain = body.section, body.section == "starter_questions"
    keyf = (lambda x: x) if plain else (lambda x: x.get(studio.SECTION_KEY[s]) if isinstance(x, dict) else None)
    idx = next((i for i, x in enumerate(items) if keyf(x) == body.key), None) if body.key is not None else None
    if body.op != "add" and idx is None:
        raise HTTPException(404, f"{studio.SECTION_LABEL[s]} '{body.key}' not found")
    if body.op != "delete":
        rec = body.record
        if plain:
            rec = str(rec or "").strip()
            if not rec:
                raise HTTPException(400, "Write the question")
        else:
            if not isinstance(rec, dict) or not str(rec.get(studio.SECTION_KEY[s]) or "").strip():
                raise HTTPException(400, f"Give the {studio.SECTION_LABEL[s].lower()} a {studio.SECTION_KEY[s]}")
        new_key = keyf(rec)
        if any(keyf(x) == new_key for i, x in enumerate(items) if i != idx):
            raise HTTPException(409, f"There is already a {studio.SECTION_LABEL[s].lower()} called '{new_key}'")
        if body.op == "add":
            items.append(rec)
        else:
            items[idx] = rec
    else:
        items.pop(idx)
    content[s] = items
    nb = save_version(db, a, b, content)
    key = body.key if body.op == "delete" else (body.record if plain else (nb.content.get(s) or [{}])[-1 if body.op == "add" else idx].get(studio.SECTION_KEY[s]))
    kind = {"add": "studio.record_added", "edit": "studio.record_edited", "delete": "studio.record_deleted"}[body.op]
    audit.record(db, a.org_id, a.actor_label, kind, nb.id, {"layer": studio.BY_ID[studio.layer_of(s)]["name"], "section": s, "record": key,
                                                            "version": nb.version, "from_version": b.version}, commit=False)
    db.commit()
    return bp_out(nb)


class EngineIn(BaseModel):
    blueprint_id: str
    action: str
    facts: dict = {}


@router.get("/{layer_id}/live")
def live(layer_id: str, a: Access = Depends(require("blueprint:view")), db: Session = Depends(get_db)):
    """What the layer is doing right now (read-only)."""
    from ..studio_live import LIVE
    _layer(layer_id)
    return LIVE[layer_id](db, a, db.get(Organisation, a.org_id))


@router.post("/engine/try")
def try_engine(body: EngineIn, a: Access = Depends(require("blueprint:view")), db: Session = Depends(get_db)):
    """Run the neuro-symbolic checks on facts the person types in. Nothing is proposed, approved or sent."""
    from .. import decisions
    b = _get(db, a, body.blueprint_id)
    act = next((x for x in (b.content or {}).get("actions") or [] if x["name"] == body.action), None)
    if not act:
        raise HTTPException(404, f"No action called {body.action}")
    ex = decisions.evaluate(b.content, body.action, body.facts, b.version)
    amount = body.facts.get(act["amount_fact"]) if act.get("amount_fact") else None
    return {"verdict": ex["verdict"], "hard": ex.get("hard", []), "gate": ex.get("gate", []), "soft": ex.get("soft", []),
            "authority": decisions.authority(a, act, amount), "risk": act["risk"], "owner_role": act.get("owner_role")}


class ResetIn(BaseModel):
    blueprint_id: str | None = None
    confirm: bool = False


@router.post("/{layer_id}/reset")
def reset(layer_id: str, body: ResetIn, a: Access = Depends(current), db: Session = Depends(get_db)):
    """Preview (confirm=false) or apply a reset of one layer: records back to what Aria XAI generated, settings to defaults."""
    L = _layer(layer_id)
    org = db.get(Organisation, a.org_id)
    can_rec, can_set = a.can("blueprint:edit"), a.can(studio.edit_permission(layer_id))
    if not (can_rec or can_set):
        raise HTTPException(403, "Your role cannot reset this layer.")
    b = _get(db, a, body.blueprint_id) if body.blueprint_id else None
    orig = studio.original(db, a.org_id)
    rec_changes = studio.record_changes(b.content or {}, orig.content or {}, L["sections"]) if (b and orig and can_rec) else []
    set_changes = studio.setting_changes(layer_id, studio.get(org, layer_id)) if can_set else []
    out = {"layer": L["name"], "original": {"id": orig.id, "version": orig.version} if orig else None,
           "changes": rec_changes + set_changes}
    if not body.confirm:
        return out
    if not out["changes"]:
        raise HTTPException(409, "This layer already matches the original")
    nb = None
    if rec_changes:
        content = {**copy.deepcopy(b.content), **{s: copy.deepcopy(orig.content.get(s) or []) for s in L["sections"]}}
        prov = {k: v for k, v in (b.provenance or {}).items() if k not in L["sections"]}
        prov.update({k: v for k, v in (orig.provenance or {}).items() if k in L["sections"]})
        nb = save_version(db, a, b, content, note=f"Reset {L['name']} to the original from v{orig.version}", prov=prov)
    if set_changes:
        st = dict(org.settings or {})
        st["studio"] = {k: v for k, v in (st.get("studio") or {}).items() if k != layer_id}
        if layer_id == "governance":
            st["redact_contact_data"] = True
        org.settings = st
    audit.record(db, a.org_id, a.actor_label, "studio.layer_reset", nb.id if nb else layer_id,
                 {"layer": L["name"], "records": [f"{c['change']} {c['label']} {c['id']}" for c in rec_changes][:50],
                  "settings": [c["id"] for c in set_changes], "original_version": orig.version if orig else None,
                  "new_version": nb.version if nb else None}, commit=False)
    db.commit()
    return {**out, "blueprint": bp_out(nb) if nb else None}
