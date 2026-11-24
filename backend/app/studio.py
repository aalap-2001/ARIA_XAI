"""Aria XAI Studio: the framework's six layers, as configuration a person can see, edit and reset.

Each layer owns two kinds of configuration:
    records   entries of the blueprint (facts, rules, agents, ...). Edited as a new blueprint version, so history is
              never lost; "reset" restores the records Aria XAI originally generated from the product.
    settings  runtime knobs stored on the organisation. "reset" restores the framework defaults.
"""
from sqlalchemy import select

from .models import Blueprint, Organisation

LAYERS = [
    {"id": "cognitive", "name": "Cognitive Core", "runs_on": "Rule engine",
     "purpose": "The rule engine. The model only states facts; soft signals weigh the evidence, the gate turns scores into true, false "
                "or unknown, and hard rules make the final, explainable verdict. Add or change rules here.",
     "sections": ["facts", "signals", "rules"], "settings": {}},
    {"id": "motivation", "name": "Motivation Engine", "runs_on": "Aria Watch · feedback loop",
     "purpose": "Observes what happens in your product, learns from the feedback your people give, and suggests improvements. "
                "Nothing it learns is applied without a person approving it.",
     "sections": ["kpis", "watch_rules"],
     "settings": {"watch_enabled": {"type": "bool", "default": True, "label": "Aria Watch observes product events"},
                  "watch_cooldown_minutes": {"type": "int", "default": 30, "min": 0, "max": 1440,
                                             "label": "Quiet period for the same item (minutes)"}}},
    {"id": "knowledge", "name": "Knowledge Fabric", "runs_on": "Memory",
     "purpose": "The team's memory: what it knows, where each memory comes from, how it is stored, and what changed recently. "
                "It fills itself from your documents, data, blueprint, conversations and decisions; there is nothing to configure.",
     "sections": ["ontology"], "readonly": True,
     "settings": {"search_results": {"type": "int", "default": 5, "min": 1, "max": 20, "label": "Document passages per search"},
                  "max_rows": {"type": "int", "default": 200, "min": 10, "max": 5000, "label": "Rows per data query"}}},
    {"id": "swarm", "name": "Swarm Orchestrator", "runs_on": "Aria Orchestrator · agents · plans",
     "purpose": "Where every request goes: Aria Orchestrator plans it, hands work to the lead agents and their specialists, and "
                "turns changes into plans a person approves. See the route, the plans and what the team has been doing.",
     "sections": ["agents"],
     "settings": {"orchestrator_steps": {"type": "int", "default": 8, "min": 2, "max": 20, "label": "Steps for Aria Orchestrator"},
                  "agent_steps": {"type": "int", "default": 10, "min": 2, "max": 30, "label": "Steps per agent"},
                  "delegation_depth": {"type": "int", "default": 2, "min": 1, "max": 3, "label": "Levels of sub-agents"}}},
    {"id": "interface", "name": "Anthropomorphic Interface", "runs_on": "Persona · chat · API · widget",
     "purpose": "The face of your business: a talking, interactive agent with its own name, role, personality and tone, the way a "
                "good sales or service person would speak for you.",
     "sections": ["starter_questions"],
     "settings": {"persona_name": {"type": "text", "default": "Aria", "max": 40, "label": "Name"},
                  "persona_role": {"type": "text", "default": "", "max": 80, "label": "Role",
                                   "hint": "For example: sales and service guide. Leave empty to use your business name."},
                  "traits": {"type": "text", "default": "warm, knowledgeable, honest, helpful", "max": 160, "label": "Personality",
                             "hint": "A few words, separated by commas"},
                  "greeting": {"type": "text", "default": "", "max": 240, "label": "Greeting",
                               "hint": "The first thing people see. Leave empty for a greeting built from the name and role."},
                  "avatar": {"type": "choice", "default": "teal", "choices": ["teal", "indigo", "amber", "rose", "slate"], "label": "Avatar colour"},
                  "tone": {"type": "choice", "default": "friendly", "choices": ["plain", "friendly", "formal"], "label": "Tone"},
                  "reply_length": {"type": "choice", "default": "standard", "choices": ["short", "standard", "detailed"], "label": "Answer length"},
                  "language": {"type": "choice", "default": "match", "choices": ["match", "English"], "label": "Language"}}},
    {"id": "governance", "name": "Governance Sentinel", "runs_on": "Soft and hard rules · policy · audit",
     "purpose": "The audit layer: the soft and hard rules every step is checked against, who may approve which action, the "
                "guardrails on every model call, and the tamper-evident record of everything that happened.",
     "sections": ["actions"],
     "settings": {"redact_contact_data": {"type": "bool", "default": True,
                                          "label": "Redact email addresses and phone numbers before data reaches an AI model"}}},
]
BY_ID = {x["id"]: x for x in LAYERS}
SECTION_LABEL = {"facts": "Fact", "signals": "Signal", "rules": "Rule", "kpis": "KPI", "watch_rules": "Watch rule",
                 "ontology": "Entity", "agents": "Agent", "starter_questions": "Starter question", "actions": "Action"}
SECTION_KEY = {"facts": "name", "signals": "id", "rules": "id", "kpis": "name", "watch_rules": "id", "ontology": "name",
               "agents": "id", "actions": "name"}
_EDITED = ("Edited from", "Refined from", "Rules uploaded", "Reset ")


def edit_permission(layer_id: str) -> str:
    """Governance guardrails are organisation policy; everything else is part of teaching the product."""
    return "org:edit" if layer_id == "governance" else "blueprint:edit"


def defaults(layer_id: str) -> dict:
    return {k: v["default"] for k, v in BY_ID[layer_id]["settings"].items()}


def get(org: Organisation, layer_id: str) -> dict:
    st = org.settings or {}
    saved = (st.get("studio") or {}).get(layer_id) or {}
    out = {**defaults(layer_id), **{k: v for k, v in saved.items() if k in BY_ID[layer_id]["settings"]}}
    if layer_id == "governance" and "redact_contact_data" in st:  # kept at the top level for older code paths
        out["redact_contact_data"] = bool(st["redact_contact_data"])
    return out


def setting(org: Organisation, layer_id: str, key: str):
    return get(org, layer_id)[key]


def clean(layer_id: str, values: dict) -> tuple[dict, list[str]]:
    spec, out, errors = BY_ID[layer_id]["settings"], {}, []
    for k, v in (values or {}).items():
        s = spec.get(k)
        if not s:
            errors.append(f"Unknown setting '{k}'")
        elif s["type"] == "bool":
            out[k] = bool(v)
        elif s["type"] == "int":
            try:
                n = int(v)
            except (TypeError, ValueError):
                errors.append(f"{s['label']} must be a whole number")
                continue
            if not s["min"] <= n <= s["max"]:
                errors.append(f"{s['label']} must be between {s['min']} and {s['max']}")
            out[k] = n
        elif s["type"] == "text":
            v = " ".join(str(v or "").split())
            if len(v) > s["max"]:
                errors.append(f"{s['label']} can be at most {s['max']} characters")
            out[k] = v
        elif s["type"] == "choice":
            if v not in s["choices"]:
                errors.append(f"{s['label']} must be one of {', '.join(s['choices'])}")
            out[k] = v
    return out, errors


def save(org: Organisation, layer_id: str, values: dict) -> dict:
    st = dict(org.settings or {})
    studio = dict(st.get("studio") or {})
    studio[layer_id] = {**get(org, layer_id), **values}
    st["studio"] = studio
    if layer_id == "governance":
        st["redact_contact_data"] = studio[layer_id]["redact_contact_data"]
    org.settings = st
    return studio[layer_id]


def original(db, org_id: str) -> Blueprint | None:
    """The latest blueprint Aria XAI generated from the product itself (not an edit, refinement, upload or reset)."""
    rows = db.execute(select(Blueprint).where(Blueprint.org_id == org_id, Blueprint.status.in_(["draft", "published", "archived"]))
                      .order_by(Blueprint.version.desc())).scalars()
    return next((b for b in rows if not (b.note or "").startswith(_EDITED)), None)


def record_changes(old: dict, new: dict, sections: list[str]) -> list[dict]:
    """What a reset would change, per record."""
    out = []
    for s in sections:
        a, b = old.get(s) or [], new.get(s) or []
        if s == "starter_questions":
            for q in b:
                if q not in a:
                    out.append({"section": s, "label": SECTION_LABEL[s], "id": q, "change": "added", "fields": []})
            for q in a:
                if q not in b:
                    out.append({"section": s, "label": SECTION_LABEL[s], "id": q, "change": "removed", "fields": []})
            continue
        k = SECTION_KEY[s]
        ai = {x.get(k): x for x in a if isinstance(x, dict)}
        bi = {x.get(k): x for x in b if isinstance(x, dict)}
        for key in bi.keys() - ai.keys():
            out.append({"section": s, "label": SECTION_LABEL[s], "id": key, "change": "added", "fields": []})
        for key in ai.keys() - bi.keys():
            out.append({"section": s, "label": SECTION_LABEL[s], "id": key, "change": "removed", "fields": []})
        for key in ai.keys() & bi.keys():
            fields = [{"field": f, "before": _brief(ai[key].get(f)), "after": _brief(bi[key].get(f))}
                      for f in sorted(set(ai[key]) | set(bi[key])) if ai[key].get(f) != bi[key].get(f)]
            if fields:
                out.append({"section": s, "label": SECTION_LABEL[s], "id": key, "change": "changed", "fields": fields})
    return out


def setting_changes(layer_id: str, current: dict) -> list[dict]:
    spec, d = BY_ID[layer_id]["settings"], defaults(layer_id)
    return [{"section": "settings", "label": "Setting", "id": spec[k]["label"], "change": "changed",
             "fields": [{"field": "value", "before": _brief(current.get(k)), "after": _brief(d[k])}]}
            for k in spec if current.get(k) != d[k]]


RECORD_SECTIONS = [s for x in LAYERS for s in x["sections"]]


def layer_of(section: str) -> str:
    return next(x["id"] for x in LAYERS if section in x["sections"])


def _index(section: str, items: list) -> dict:
    if section == "starter_questions":
        return {q: q for q in items if isinstance(q, str)}
    return {x.get(SECTION_KEY[section]): x for x in items if isinstance(x, dict)}


def provenance(old_content: dict, old_prov: dict | None, new_content: dict, actor: str) -> dict:
    """Carry each record's origin into a new version. Unchanged records keep it; added or changed ones are the person's."""
    from datetime import datetime, timezone
    at = datetime.now(timezone.utc).isoformat()
    out = {}
    for s in RECORD_SECTIONS:
        old, new, prev = _index(s, old_content.get(s) or []), _index(s, new_content.get(s) or []), (old_prov or {}).get(s) or {}
        sec = {}
        for k, rec in new.items():
            if k in old and old[k] == rec:
                if k in prev:
                    sec[k] = prev[k]
            else:
                sec[k] = {"kind": "human", "by": actor, "at": at, "change": "edited" if k in old else "added"}
        if sec:
            out[s] = sec
    return out


def _brief(v) -> str:
    import json
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    return s if len(s) <= 140 else s[:137] + "..."


def persona(org: Organisation) -> dict:
    """How the agent team presents itself to people, with sensible defaults built from the business."""
    st = get(org, "interface")
    name = st["persona_name"] or "Aria"
    role = st["persona_role"] or f"{org.name.replace(' (demo)', '')} sales and service guide"
    greeting = st["greeting"] or f"Hi, I'm {name}, your {role}. What can I help you with today?"
    traits = [t.strip() for t in (st["traits"] or "").split(",") if t.strip()]
    return {"name": name, "role": role, "greeting": greeting, "traits": traits, "avatar": st["avatar"], "tone": st["tone"]}
