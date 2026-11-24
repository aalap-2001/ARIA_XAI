"""Understand a product from what the customer gives us: a description, documents and data.
No industry is ever selected; it is inferred and written into the blueprint as an output.

    gather inputs → LLM proposes a blueprint (tool call) → symbolic validation
        → if errors: LLM repairs with the errors in hand (max 2 rounds) → draft for human review
"""
import json
import threading
import traceback

from sqlalchemy import func, select

from . import audit
from . import blueprint as BP
from .db import SessionLocal
from .knowledge import corpus_digest
from .llm.base import LLMError
from .llm.service import default_llm
from .models import Blueprint, DataConnection, Organisation
from .sentinel_bridge import redact

SYSTEM = """You are Aria XAI's product-understanding engine. A business has connected its product to Aria XAI so that it can be
run by a team of AI agents governed by symbolic rules. From the description, documents and data schemas you are given,
work out what the business is and design its operating blueprint.

Principles:
- Infer the industry, users and workflows yourself. Never assume a domain the evidence does not support.
- Ground everything in the inputs. Hard rules must come from the documents (cite "filename p.N") or from data constraints;
  do not invent regulations.
- Facts are the typed vocabulary decisions are judged on (snake_case). Rules and signals may only reference facts
  (or signals.<id> for gated signals). Use numbers and booleans wherever a rule needs to compare.
- Actions are things that change the outside world (UPPER_SNAKE_CASE). Pick a risk level honestly. Use
  auto_approve_below only when an amount threshold is clearly safe; use always_review for irreversible or sensitive actions.
  Give every action an owner_role chosen from the organisation's roles (the people accountable for that area).
  If an action is clearly a single-row INSERT or UPDATE on one connected table, give it a database executor with the
  exact table, key column and the only columns it may write; otherwise use a webhook executor.
- The platform has three built-in agents: Aria (orchestrator), Aria Analyst (reads) and Aria Executor (the only agent that
  writes, always after a human approves). Design a small, sharp team of specialist sub-agents (typically 2-5) they can
  delegate to: each with a clear purpose, the minimum read tools it needs, a data_scope that uses the real connection ids and
  table names given, and the actions it is expert in.
- Watch rules tell Aria Watch which product events deserve attention. Be selective: only events where a change could clearly
  benefit the business or prevent a loss (e.g. large or unusual values, failures, policy breaches). Never watch everything.
- Starter questions are what a real user of this product would ask the team on day one.
Call the submit_blueprint tool exactly once with the complete blueprint. Do not reply with prose."""


def _inputs(db, org_id: str) -> dict:
    org = db.get(Organisation, org_id)
    conns = db.execute(select(DataConnection).where(DataConnection.org_id == org_id, DataConnection.status == "ready")).scalars().all()
    contact = (org.settings or {}).get("redact_contact_data", True)
    data = []
    for c in conns:
        snap = c.schema_snapshot or {}
        data.append({"connection_id": c.id, "name": c.name, "kind": c.kind,
                     "tables": [{"name": t["name"], "rows": t.get("rows"), "columns": [f"{x['name']} {x['type']}" for x in t.get("columns", [])],
                                 "primary_key": t.get("primary_key"), "foreign_keys": t.get("foreign_keys"),
                                 "sample_rows": redact(t.get("sample", [])[:3], contact)} for t in snap.get("tables", [])[:60]],
                     "endpoints": snap.get("endpoints", [])[:60]})
    return {"description": org.product_description or "", "documents": corpus_digest(db, org_id), "data": data, "org_name": org.name,
            "roles": sorted(role_names(db, org_id))}


def role_names(db, org_id) -> set:
    from .models import Role
    return {r for (r,) in db.execute(select(Role.name).where(Role.org_id == org_id))}


def _ask(llm, messages, purpose) -> dict:
    tool = {"name": "submit_blueprint", "description": "Submit the complete product blueprint.", "parameters": BP.SCHEMA}
    for attempt in range(2):
        r = llm.chat(SYSTEM, messages, [tool], purpose=purpose, max_tokens=16000)
        call = next((t for t in r.tool_calls if t.name == "submit_blueprint"), None)
        if call and "_invalid_json" not in call.args:
            return call.args
        messages = messages + [r.as_message(), *([{"role": "tool", "tool_call_id": t.id, "name": t.name, "content": "Invalid; call submit_blueprint again with valid JSON.", "is_error": True} for t in r.tool_calls]),
                               *([] if r.tool_calls else [{"role": "user", "content": "Call the submit_blueprint tool now with the complete blueprint."}])]
    raise LLMError("The model did not return a blueprint. Try again, or choose a more capable default model.")


def generate(org_id: str, bp_id: str, actor: str, refine: dict | None = None):
    """Runs in a background thread with its own database session."""
    db = SessionLocal()
    bp = db.get(Blueprint, bp_id)

    def step(msg, state="done"):
        bp.progress = [*(bp.progress or []), {"step": msg, "state": state}]
        db.commit()

    try:
        llm = default_llm(db, org_id)
        inputs = _inputs(db, org_id)
        if not (inputs["description"].strip() or inputs["documents"] or inputs["data"]):
            raise LLMError("Give Aria XAI something to understand: describe the product, upload documents or connect data.")
        step(f"Read {len(inputs['documents'])} document(s), {len(inputs['data'])} data connection(s) and the product description")
        bp.sources = {"documents": [d["document"] for d in inputs["documents"]], "connections": [d["name"] for d in inputs["data"]],
                      "described": bool(inputs["description"].strip()), "model": f"{llm.conn.provider}/{llm.model}"}
        conns = connections_index(db, org_id)
        roles = set(inputs["roles"])
        if refine:
            prompt = (f"Here is the current blueprint:\n{json.dumps(refine['current'])}\n\nRevise it per this instruction from the "
                      f"product team{(' (focus on the ' + refine['section'] + ' section)') if refine.get('section') else ''}:\n"
                      f"{refine['instruction']}\n\nKeep everything else unchanged. Context about the product follows.\n\n{json.dumps(inputs)[:120000]}")
            step("Asked the model to refine the blueprint")
        else:
            prompt = "Understand this product and design its blueprint.\n\n" + json.dumps(inputs, default=str)[:160000]
            step(f"Asked {llm.conn.provider} / {llm.model} to infer the business, rules, actions and agent team")
        messages = [{"role": "user", "content": prompt}]
        content = BP.normalise(_ask(llm, messages, "understanding"))
        result = BP.validate(content, conns, roles)
        step(f"Symbolic check: {len(result['errors'])} error(s), {len(result['warnings'])} warning(s)")
        for round_ in range(2):
            if result["ok"]:
                break
            step(f"Repair round {round_ + 1}: sent the errors back to the model")
            fix = [{"role": "user", "content": prompt},
                   {"role": "user", "content": "Your previous blueprint failed symbolic validation:\n- " + "\n- ".join(result["errors"]) +
                    f"\n\nPrevious blueprint:\n{json.dumps(content)}\n\nFix every error and call submit_blueprint with the corrected complete blueprint."}]
            content = BP.normalise(_ask(llm, [{"role": "user", "content": fix[0]["content"] + "\n\n" + fix[1]["content"]}], "understanding_repair"))
            result = BP.validate(content, conns, roles)
            step(f"Symbolic check: {len(result['errors'])} error(s), {len(result['warnings'])} warning(s)")
        if refine and refine.get("current"):
            for a in content.get("actions", []):  # keep configured webhook URLs across refinements
                old = next((x for x in refine["current"].get("actions", []) if x.get("name") == a["name"]), None)
                old_url = old and ((old.get("executor") or {}).get("url") or old.get("webhook_url"))
                if old_url and a["executor"].get("type") == "webhook" and not a["executor"].get("url"):
                    a["executor"]["url"] = old_url
        bp.content, bp.validation, bp.status = content, result, "draft"
        step(f"Draft ready, inferred: {content.get('industry', 'unknown')}; {len(content.get('agents', []))} agents, "
             f"{len(content.get('rules', []))} rules, {len(content.get('actions', []))} actions")
        audit.record(db, org_id, actor, "blueprint.generated", bp.id, {"version": bp.version, "industry": content.get("industry"),
                                                                       "errors": len(result["errors"]), "refine": bool(refine)})
    except LLMError as ex:
        bp.status, bp.error = "failed", str(ex)
        step(str(ex), "failed")
    except Exception as ex:  # noqa: BLE001
        bp.status, bp.error = "failed", f"{type(ex).__name__}: {ex}"
        step("Unexpected error", "failed")
        traceback.print_exc()
    finally:
        db.commit()
        db.close()


def start(db, org_id: str, actor_id: str, actor: str, refine: dict | None = None, note: str = "") -> Blueprint:
    v = (db.execute(select(func.max(Blueprint.version)).where(Blueprint.org_id == org_id)).scalar() or 0) + 1
    bp = Blueprint(org_id=org_id, version=v, status="generating", progress=[], created_by=actor_id, note=note[:500])
    db.add(bp)
    db.commit()
    threading.Thread(target=generate, args=(org_id, bp.id, actor, refine), daemon=True).start()
    return bp


def connections_index(db, org_id) -> dict:
    conns = db.execute(select(DataConnection).where(DataConnection.org_id == org_id)).scalars().all()
    return {c.id: {"tables": {t["name"]: [x["name"] for x in t.get("columns", [])] for t in (c.schema_snapshot or {}).get("tables", [])},
                   "endpoints": (c.schema_snapshot or {}).get("endpoints", []), "allow_writes": bool((c.config or {}).get("allow_writes"))}
            for c in conns}
