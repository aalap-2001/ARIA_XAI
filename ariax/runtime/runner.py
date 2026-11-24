"""Agent runner, executes an agent's playbook through the four subsystems.

The playbook is product logic declared in the bundle (what to do). The runner contains no
domain vocabulary: every step is one of fetch / recall / reason / evaluate / act / remember,
and each step can only reach the world through the governed subsystem that owns it.
"""
import json
import traceback

from ..core import expr
from ..core.errors import AriaError
from ..core.identity import Principal
from ..core.ids import new_id, now_iso
from ..sentinel import rails

SUBSYSTEM = {"fetch": "connectors", "recall": "fabric", "remember": "fabric", "reason": "sentinel",
             "evaluate": "rules", "act": "sentinel"}


class AgentRunner:
    def __init__(self, platform):
        self.p = platform
        platform.store.executescript("""
        CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, trace_id TEXT, domain TEXT, agent TEXT, case_id TEXT,
            status TEXT, verdict TEXT, action TEXT, decision_id TEXT, effect TEXT, timeline TEXT, started_at TEXT,
            finished_at TEXT, outcome TEXT, score REAL, error TEXT, bundle_version TEXT, principal TEXT);
        CREATE TABLE IF NOT EXISTS explanations (id TEXT PRIMARY KEY, run_id TEXT, trace_id TEXT, decision_id TEXT,
            domain TEXT, body TEXT, hash TEXT, at TEXT);
        """)

    # ------------------------------------------------------------------ helpers
    def agent_card(self, bundle, agent_id):
        card = next((a for a in (bundle.get("agents") or {}).get("agents") or [] if a["id"] == agent_id), None)
        if not card:
            raise AriaError(f"No agent '{agent_id}' in domain '{bundle['manifest']['domain']}'")
        return card

    def list_cases(self, domain, agent_id):
        bundle = self.p.bundles.active(domain)
        card = self.agent_card(bundle, agent_id)
        src = card.get("case_source")
        if not src:
            return []
        principal = Principal(tenant=bundle["manifest"]["tenant"], service=domain, agent=agent_id, on_behalf_of="console")
        return self.p.connectors.get(src["connector"], principal).invoke(src["operation"], {}) or []

    # ------------------------------------------------------------------ run
    def run(self, domain: str, agent_id: str, case_id: str, on_behalf_of: str | None = None, inputs: dict | None = None) -> dict:
        p = self.p
        bundle = p.bundles.active(domain)
        version = bundle["manifest"]["version"]
        card = self.agent_card(bundle, agent_id)
        # Edge: trace_id minted, Principal constructed once.
        principal = Principal(tenant=bundle["manifest"]["tenant"], service=domain, agent=agent_id, case=str(case_id),
                              on_behalf_of=on_behalf_of or card.get("default_on_behalf_of"))
        run_id = new_id("run")
        timeline = []

        def ev(subsystem, title, detail=None, status="ok"):
            timeline.append({"at": now_iso(), "subsystem": subsystem, "title": title, "status": status, "detail": detail})

        p.store.execute("INSERT INTO runs (run_id, trace_id, domain, agent, case_id, status, started_at, bundle_version, principal) VALUES (?,?,?,?,?,?,?,?,?)",
                        (run_id, principal.trace_id, domain, agent_id, str(case_id), "running", now_iso(), version, json.dumps(principal.to_dict())))
        ev("edge", "Principal constructed, trace minted", principal.to_dict())
        ctx = {"case": {"id": str(case_id)}, "inputs": inputs or {}, "agent": {"id": agent_id}}
        shown, passed_over, explanation, result = [], [], None, None
        status, error = "completed", None
        try:
            p.sentinel.assert_alive(domain, agent_id)
            for i, step in enumerate(card.get("playbook") or []):
                kind = step["step"]
                label = step.get("label") or kind
                if step.get("when"):
                    ok, _ = expr.evaluate(step["when"], ctx)
                    if ok is not True:
                        ev(SUBSYSTEM[kind], f"Skipped: {label}", {"when": expr.describe(step["when"])}, "skipped")
                        continue
                if kind == "fetch":
                    handle = p.connectors.get(step["connector"], principal)
                    args = expr.resolve(step.get("args") or {"case": "$case.id"}, ctx)
                    data = handle.invoke(step["operation"], args)
                    ctx[step["as"]] = data
                    p.fabric.short_term.put(principal.trace_id, step["as"], data)
                    flags = rails.scan_injection(data)
                    p.fabric.record_episode(principal, "observation", observation=f"{step['connector']}.{step['operation']}",
                                            action="fetch", outcome="found" if data is not None else "empty")
                    ev("connectors", f"{label}, resolved '{step['connector']}' ({handle.instance.get('system') or handle.instance.get('type')}) by name",
                       {"operation": step["operation"], "result": data, "injection_flags": flags},
                       "warn" if (data is None or flags) else "ok")
                elif kind == "recall":
                    q = {"entity": step["entity"], "subject": expr.resolve(step.get("subject"), ctx), "predicate": step.get("predicate")}
                    q = {k: v for k, v in q.items() if v}
                    akt = expr.resolve(step.get("as_known_at"), ctx) if step.get("as_known_at") else None
                    answers = p.fabric.query(q, principal, as_known_at=akt)
                    top = answers[: step.get("top_k", 1)]
                    shown += [{"id": a["id"], "subject": a["subject"], "value": a["value"], "source": a["source"]} for a in top]
                    passed_over += [{"id": a["id"]} for a in answers[len(top):]]
                    ctx[step["as"]] = top[0]["value"] if top else None
                    ctx[step["as"] + "_answer"] = top[0] if top else None
                    p.fabric.record_episode(principal, "observation", observation=f"queried {step['entity']} {q.get('subject', '')}",
                                            action="recall", outcome=f"{len(answers)} answers")
                    ev("fabric", f"{label}, {step['entity']} as known at {akt or 'now'}",
                       {"query": q, "answers": answers[:3], "row_level_scope": answers[0]["visible_to"] if answers else None},
                       "ok" if answers else "warn")
                elif kind == "reason":
                    context = {k: ctx.get(k) for k in step.get("include") or []}
                    res = p.sentinel.gateway.complete(principal=principal, policy=(bundle.get("policies") or {}).get("model_policy"),
                                                      instruction=step["instruction"], context=context)
                    ctx[step.get("as", "analysis")] = res["text"]
                    p.fabric.record_episode(principal, "reasoning", observation=step["instruction"][:200], action="reason",
                                            outcome=res["text"][:500], data={"model": res["model"], "redactions": res["redactions_in"]})
                    ev("sentinel", f"{label}, model call through the gateway", res,
                       "warn" if res["injection_flags"] or res.get("error") else "ok")
                elif kind == "evaluate":
                    explanation = p.rules.evaluate(bundle.get("rules") or {}, ctx, version)
                    ctx["verdict"] = explanation["verdict"]
                    ctx["signals"] = {g["signal"]: g["outcome"] for g in explanation["gate"]}
                    ev("rules", f"{label}, soft → gate → hard: {explanation['verdict']}", explanation,
                       "ok" if explanation["verdict"] == "VALID" else "warn")
                elif kind == "remember":
                    ingest = Principal(tenant=principal.tenant, service=domain, agent=agent_id, case=principal.case, trace_id=principal.trace_id)
                    r = p.fabric.remember({"entity": step["entity"], "subject": expr.resolve(step["subject"], ctx),
                                           "predicate": step.get("predicate", "value"), "value": expr.resolve(step["value"], ctx),
                                           "case_id": principal.case}, {"source": f"agent:{agent_id}", "locator": run_id}, ingest)
                    ev("fabric", f"{label}, remembered {step['entity']}", r)
                elif kind == "act":
                    verdict = ctx.get("verdict") or "INSUFFICIENT_EVIDENCE"
                    action = (step.get("by_verdict") or {}).get(verdict) or step.get("action")
                    if not action:
                        ev("sentinel", "No action mapped for verdict", {"verdict": verdict}, "skipped")
                        continue
                    amount = expr.resolve(step.get("amount"), ctx) if step.get("amount") else None
                    payload = expr.resolve(step.get("payload") or {}, ctx)
                    payload.update({"case": principal.case, "action": action, "verdict": verdict})
                    decisions = (bundle.get("fabric") or {}).get("decisions") or []
                    retention = int(((bundle.get("fabric") or {}).get("retention") or {}).get("receipts_days", 90))

                    def hook(decision_id, _action=action):
                        if _action in decisions:
                            rc = p.fabric.write_receipt(principal, decision_id, shown, passed_over, {
                                "bundle_version": version, "model": p.sentinel.gateway.status()["model"],
                                "as_known_at": now_iso(), "agent": agent_id, "action": _action}, retention)
                            ev("fabric", "Decision boundary, receipt written", rc)
                        if explanation:
                            p.store.execute("INSERT INTO explanations VALUES (?,?,?,?,?,?,?,?)", (
                                new_id("ex"), run_id, principal.trace_id, decision_id, domain,
                                json.dumps(explanation, default=str), explanation["hash"], now_iso()))

                    result = p.sentinel.governed_step(principal=principal, bundle=bundle, agent_card=card, action_name=action,
                                                      payload=payload, amount=amount, verdict=verdict, signals=ctx.get("signals"),
                                                      run_id=run_id, evidence_hook=hook)
                    ctx["decision"] = result
                    p.fabric.record_episode(principal, "decision", observation=f"verdict {verdict}", action=action,
                                            outcome=result["status"], decision_id=result["decision_id"])
                    ev("sentinel", f"{action}, {result['risk']} risk via {result['path']}: {result['effect']}", result,
                       {"ALLOW": "ok", "REVIEW": "review", "BLOCK": "blocked"}[result["effect"]])
                    if result.get("transmission"):
                        ev("connectors", "Governed egress, sent with decision_id", result["transmission"])
        except AriaError as ex:
            status, error = "failed", f"{ex.code}: {ex.message}"
            ev("platform", "Run stopped", ex.to_dict(), "blocked")
        except Exception as ex:  # noqa: BLE001
            status, error = "failed", f"{type(ex).__name__}: {ex}"
            ev("platform", "Run failed", {"error": error, "trace": traceback.format_exc()[-1500:]}, "blocked")
        p.fabric.checkpoint(principal.case, {"run_id": run_id, "status": status, "verdict": ctx.get("verdict")}, principal)
        dec = ctx.get("decision") or {}
        p.store.execute("UPDATE runs SET status=?, verdict=?, action=?, decision_id=?, effect=?, timeline=?, finished_at=?, error=? WHERE run_id=?",
                        (status, ctx.get("verdict"), _action_of(dec, p) if dec else None, dec.get("decision_id"), dec.get("effect"),
                         json.dumps(timeline, default=str), now_iso(), error, run_id))
        return self.get(run_id)

    def get(self, run_id):
        r = self.p.store.one("SELECT * FROM runs WHERE run_id=?", (run_id,))
        if not r:
            raise AriaError(f"No run {run_id}")
        r["timeline"] = json.loads(r["timeline"]) if r["timeline"] else []
        r["principal"] = json.loads(r["principal"]) if r["principal"] else None
        if r["decision_id"]:
            r["decision"] = self.p.sentinel.decision(r["decision_id"])
        return r

    def list(self, domain=None, limit=100):
        if domain:
            return self.p.store.all("SELECT run_id, trace_id, domain, agent, case_id, status, verdict, action, decision_id, effect, started_at, outcome, score, error FROM runs WHERE domain=? ORDER BY started_at DESC LIMIT ?", (domain, limit))
        return self.p.store.all("SELECT run_id, trace_id, domain, agent, case_id, status, verdict, action, decision_id, effect, started_at, outcome, score, error FROM runs ORDER BY started_at DESC LIMIT ?", (limit,))

    def record_outcome(self, run_id: str, outcome: str) -> dict:
        """Outcome arrives later; it is linked back to the trajectory and scored by the evaluator."""
        r = self.get(run_id)
        bundle = self.p.bundles.active(r["domain"])
        ev = bundle.get("evaluator") or {}
        score = 1.0 if outcome in (ev.get("success_outcomes") or []) else 0.0 if outcome in (ev.get("failure_outcomes") or []) else 0.5
        pr = r["principal"]
        principal = Principal(tenant=pr["tenant"], service=pr["service"], agent=pr["agent"], case=pr["case"], trace_id=pr["trace_id"])
        self.p.fabric.record_episode(principal, "outcome", observation=f"outcome reported for {r['action']}", action=r["action"],
                                     outcome=outcome, decision_id=r["decision_id"], data={"score": score, "run_id": run_id})
        self.p.store.execute("UPDATE runs SET outcome=?, score=? WHERE run_id=?", (outcome, score, run_id))
        return {"run_id": run_id, "outcome": outcome, "score": score}


def _action_of(dec, p):
    d = p.sentinel.decision(dec.get("decision_id")) if dec.get("decision_id") else None
    return d["action"] if d else None
