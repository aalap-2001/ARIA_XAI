"""The declarative condition + path language shared by every subsystem.

Bundles declare WHAT (paths, comparisons, thresholds). This file is the only HOW.
It contains no domain vocabulary and no way for a bundle to define new behaviour.

Condition forms:
    {"all": [c, ...]}   {"any": [c, ...]}   {"not": c}
    {"path": "a.b", "op": "<=", "value": 0.43}
    {"path": "a.b", "exists": true}
    {"path": "a.b", "is": true}
Values may reference the context: "$a.b". Strings may interpolate: "{a.b}:{c}".
Evaluation is three-valued: True, False, or None (a referenced value was missing).
"""
import re

_REF = re.compile(r"^\$[\w.\-]+$")
_INTERP = re.compile(r"\{([\w.\-]+)\}")


def get_path(obj, path):
    if path in (None, ""):
        return obj
    cur = obj
    for key in str(path).split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list) and key.isdigit():
            idx = int(key)
            cur = cur[idx] if idx < len(cur) else None
        else:
            cur = getattr(cur, key, None)
    return cur


def resolve(value, ctx):
    if isinstance(value, str):
        if _REF.match(value):
            return get_path(ctx, value[1:])
        if "{" in value:
            return _INTERP.sub(lambda m: "" if get_path(ctx, m.group(1)) is None else str(get_path(ctx, m.group(1))), value)
        return value
    if isinstance(value, list):
        return [resolve(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: resolve(v, ctx) for k, v in value.items()}
    return value


def _cmp(op, a, b):
    try:
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        if op == "in":
            return a in (b or [])
        if op == "contains":
            return b in (a or [])
    except TypeError:
        return None
    raise ValueError(f"Unknown operator: {op}")


OPERATORS = ["==", "!=", "<", "<=", ">", ">=", "in", "contains"]


def evaluate(cond, ctx, trace=None):
    """Returns (result, trace). result is True / False / None (unknown)."""
    trace = [] if trace is None else trace
    if cond is None:
        return True, trace
    if "all" in cond:
        unknown = False
        for c in cond["all"]:
            r, _ = evaluate(c, ctx, trace)
            if r is False:
                return False, trace
            unknown |= r is None
        return (None if unknown else True), trace
    if "any" in cond:
        unknown = False
        for c in cond["any"]:
            r, _ = evaluate(c, ctx, trace)
            if r is True:
                return True, trace
            unknown |= r is None
        return (None if unknown else False), trace
    if "not" in cond:
        r, _ = evaluate(cond["not"], ctx, trace)
        return (None if r is None else not r), trace
    if "path" in cond:
        actual = get_path(ctx, cond["path"])
        if "exists" in cond:
            result = (actual is not None) == bool(cond["exists"])
            op, expected = "exists", cond["exists"]
        elif actual is None:
            result, op, expected = None, cond.get("op", "is"), cond.get("value", cond.get("is"))
        elif "is" in cond:
            result, op, expected = actual == cond["is"], "is", cond["is"]
        else:
            expected = resolve(cond.get("value"), ctx)
            op = cond.get("op", "==")
            result = _cmp(op, actual, expected)
        trace.append({"path": cond["path"], "op": op, "expected": expected, "actual": actual, "result": result})
        return result, trace
    raise ValueError(f"Unrecognised condition: {cond!r}")


def describe(cond) -> str:
    if not cond:
        return "always"
    if "all" in cond:
        return "(" + " AND ".join(describe(c) for c in cond["all"]) + ")"
    if "any" in cond:
        return "(" + " OR ".join(describe(c) for c in cond["any"]) + ")"
    if "not" in cond:
        return "NOT " + describe(cond["not"])
    if "exists" in cond:
        return f"{cond['path']} {'exists' if cond['exists'] else 'is missing'}"
    if "is" in cond:
        return f"{cond['path']} is {cond['is']}"
    return f"{cond['path']} {cond.get('op', '==')} {cond.get('value')}"


def validate_condition(cond, where: str, errors: list):
    """Schema check for a condition tree (used by bundle validation)."""
    if cond is None:
        return
    if not isinstance(cond, dict):
        errors.append(f"{where}: condition must be a mapping")
        return
    keys = set(cond)
    if keys & {"all", "any"}:
        k = "all" if "all" in cond else "any"
        if not isinstance(cond[k], list) or not cond[k]:
            errors.append(f"{where}: '{k}' must be a non-empty list")
            return
        for i, c in enumerate(cond[k]):
            validate_condition(c, f"{where}.{k}[{i}]", errors)
    elif "not" in keys:
        validate_condition(cond["not"], f"{where}.not", errors)
    elif "path" in keys:
        if not ({"op", "exists", "is"} & keys):
            errors.append(f"{where}: needs one of op/exists/is")
        if "op" in cond and cond["op"] not in OPERATORS:
            errors.append(f"{where}: unknown operator '{cond['op']}'")
    else:
        errors.append(f"{where}: unrecognised condition {sorted(keys)}")
