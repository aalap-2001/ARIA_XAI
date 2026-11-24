"""Rule Engine (Verax), how the system reasons and validates.

    features ──► SOFT engine (rank / combine evidence → continuous scores)
                      │
                      ▼
                 DISCRETIZATION GATE (score → TRUE / FALSE / INSUFFICIENT_EVIDENCE;
                      │                 uncertainty discarded irreversibly here)
                      ▼
                 HARD engine (deterministic rules over features + gated booleans only)
                      │
                      ▼
                 verdict: VALID / INVALID / INSUFFICIENT_EVIDENCE   +  Explanation bundle

Proposal ≠ disposal: a VALID verdict is not permission to act. Sentinel decides that.
There is no code path from soft output to hard input that skips the gate: the hard engine
only accepts a GatedSignals object, and only the Gate can mint one.
"""
from ..core import expr
from ..core.errors import GateViolation
from ..core.ids import canonical, sha256

_GATE_TOKEN = object()  # module-private capability: only Gate holds it


class GatedSignals:
    __slots__ = ("values", "record", "_token")

    def __init__(self, values: dict, record: list, _token=None):
        if _token is not _GATE_TOKEN:
            raise GateViolation("GatedSignals can only be produced by the Discretization Gate")
        object.__setattr__(self, "values", dict(values))
        object.__setattr__(self, "record", list(record))
        object.__setattr__(self, "_token", _token)

    def __setattr__(self, *_):
        raise GateViolation("GatedSignals are immutable")


def extract_features(rules: dict, ctx: dict) -> dict:
    out = {}
    for name, spec in (rules.get("features") or {}).items():
        raw = expr.get_path(ctx, spec.get("from"))
        ftype = spec.get("type", "number")
        val = None
        if raw is not None:
            try:
                if ftype == "bool":
                    val = bool(raw) if not isinstance(raw, str) else raw.lower() in ("true", "yes", "1", "y")
                elif ftype == "number":
                    val = float(raw)
                else:
                    val = raw
            except (TypeError, ValueError):
                val = None
        conf = expr.get_path(ctx, spec["confidence_from"]) if spec.get("confidence_from") else None
        out[name] = {"value": val, "from": spec.get("from"), "type": ftype,
                     "extraction_confidence": conf if conf is not None else (1.0 if val is not None else None),
                     "description": spec.get("description", "")}
    return out


COMBINERS = ("weighted_sum", "noisy_or")


class SoftEngine:
    """Evidence combination over normalised features.

    weighted_sum  score = sum(w * x) / sum(|w|) over the evidence present
    noisy_or      score = 1 - prod(1 - w * x): each piece of evidence independently raises the
                  probability; weights are each input's strength in 0..1
    """

    def score(self, soft_rules: list, features: dict) -> dict:
        out = {}
        for rule in soft_rules or []:
            combine = rule.get("combine", "weighted_sum")
            total_w = sum(abs(i.get("weight", 1)) for i in rule.get("inputs") or []) or 1
            acc, used_w, contribs = 0.0, 0.0, []
            not_any = 1.0  # noisy-OR: probability that no present evidence fires
            for inp in rule.get("inputs") or []:
                f = features.get(inp["feature"]) or {}
                v = f.get("value")
                w = float(inp.get("weight", 1))
                if v is None:
                    contribs.append({"feature": inp["feature"], "weight": w, "value": None, "contribution": None, "note": "missing"})
                    continue
                x = 1.0 if v is True else 0.0 if v is False else float(v)
                lo, hi = inp.get("min", 0.0), inp.get("max", 1.0)
                x = 0.0 if hi == lo else min(1.0, max(0.0, (x - lo) / (hi - lo)))
                if inp.get("invert"):
                    x = 1.0 - x
                conf = f.get("extraction_confidence") or 1.0
                x *= conf if inp.get("weight_by_confidence") else 1.0
                acc += w * x
                used_w += abs(w)
                if combine == "noisy_or":
                    p = min(1.0, max(0.0, w)) * x
                    not_any *= 1.0 - p
                    contribs.append({"feature": inp["feature"], "weight": w, "value": v, "normalised": round(x, 4), "contribution": round(p, 4)})
                else:
                    contribs.append({"feature": inp["feature"], "weight": w, "value": v, "normalised": round(x, 4), "contribution": round(w * x / total_w, 4)})
            if not used_w:
                score = None
            elif combine == "noisy_or":
                score = 1.0 - not_any
            else:
                score = acc / used_w
            out[rule["output"]] = {"rule": rule["id"], "version": rule.get("version", "1"), "combine": combine,
                                   "score": None if score is None else round(score, 4),
                                   "coverage": round(used_w / total_w, 3), "contributions": contribs,
                                   "description": rule.get("description", "")}
        return out


class Gate:
    """A versioned, owned boundary where continuous evidence becomes a discrete durable assertion."""

    def discretise(self, thresholds: list, scores: dict) -> GatedSignals:
        values, record = {}, []
        for t in thresholds or []:
            s = scores.get(t["from"]) or {}
            score, cov = s.get("score"), s.get("coverage", 0)
            min_cov = t.get("min_coverage", 0.6)
            if score is None or cov < min_cov:
                v, why = None, f"coverage {cov} below {min_cov}" if score is not None else "no evidence"
            elif score >= t["assert_above"]:
                v, why = True, f"{score} ≥ {t['assert_above']}"
            elif score <= t["deny_below"]:
                v, why = False, f"{score} ≤ {t['deny_below']}"
            else:
                v, why = None, f"{t['deny_below']} < {score} < {t['assert_above']}"
            values[t["signal"]] = v
            record.append({"signal": t["signal"], "from": t["from"], "score": score, "coverage": cov,
                           "assert_above": t["assert_above"], "deny_below": t["deny_below"], "version": t.get("version", "1"),
                           "outcome": {True: "TRUE", False: "FALSE", None: "INSUFFICIENT_EVIDENCE"}[v], "why": why})
        # The continuous scores stop here. Only booleans (or unknown) cross the boundary.
        return GatedSignals(values, record, _token=_GATE_TOKEN)


class HardEngine:
    """Deterministic validation. Accepts declared features and gated signals, never raw scores."""

    def validate(self, hard_rules: list, features: dict, gated: GatedSignals) -> dict:
        if not isinstance(gated, GatedSignals) or getattr(gated, "_token", None) is not _GATE_TOKEN:
            raise GateViolation("The hard engine only accepts output of the Discretization Gate")
        ctx = {k: v.get("value") for k, v in features.items()}
        ctx["signals"] = gated.values
        results = []
        for rule in hard_rules or []:
            when_ok = True
            if rule.get("when"):
                when_ok, _ = expr.evaluate(rule["when"], ctx)
            if when_ok is not True:
                results.append({"id": rule["id"], "version": rule.get("version", "1"), "applies": False, "status": "NOT_APPLICABLE",
                                "description": rule.get("description", ""), "citation": rule.get("citation")})
                continue
            res, trace = expr.evaluate(rule["require"], ctx)
            status = "PASS" if res is True else ("INSUFFICIENT_EVIDENCE" if res is None else rule.get("on_fail", "INVALID"))
            results.append({"id": rule["id"], "version": rule.get("version", "1"), "applies": True, "status": status,
                            "description": rule.get("description", ""), "citation": rule.get("citation"),
                            "message": rule.get("message") if status != "PASS" else None,
                            "condition": expr.describe(rule["require"]), "trace": trace})
        statuses = [r["status"] for r in results]
        verdict = "INVALID" if "INVALID" in statuses else "INSUFFICIENT_EVIDENCE" if "INSUFFICIENT_EVIDENCE" in statuses else "VALID"
        return {"verdict": verdict, "results": results}


class RuleEngine:
    def __init__(self):
        self.soft, self.gate, self.hard = SoftEngine(), Gate(), HardEngine()

    def evaluate(self, rules: dict, ctx: dict, bundle_version: str) -> dict:
        features = extract_features(rules, ctx)
        scores = self.soft.score(rules.get("soft"), features)
        gated = self.gate.discretise(rules.get("thresholds"), scores)
        hard = self.hard.validate(rules.get("hard"), features, gated)
        explanation = {
            "verdict": hard["verdict"],
            "features": features,
            "soft": scores,
            "gate": gated.record,
            "hard": hard["results"],
            "rule_versions": {r["id"]: r.get("version", "1") for r in (rules.get("soft") or []) + (rules.get("hard") or [])},
            "bundle_version": bundle_version,
            "principle": "proposal ≠ disposal, VALID is not permission to act",
        }
        explanation["hash"] = sha256(canonical(explanation))
        return explanation
