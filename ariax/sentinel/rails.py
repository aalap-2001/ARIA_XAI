"""Rails: strip sensitive data on the way in, check for leakage on the way out, flag injected
instructions in untrusted content. Patterns are generic; fields to strip come from the bundle."""
import re

PII_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "phone": re.compile(r"(?<![\w-])(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
}

INJECTION_PATTERNS = [
    re.compile(p, re.I) for p in [
        r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
        r"disregard (the |your )?(system|previous) (prompt|instructions)",
        r"you are now (a|an|in) ",
        r"reveal (your|the) (system prompt|instructions)",
        r"(approve|authori[sz]e|release|pay) (this|the) \w+ immediately",
        r"do not (tell|inform) (the )?(reviewer|auditor|user)",
        r"bypass (the )?(policy|review|guardrail)",
    ]
]


def strip(obj, fields: list[str] | None = None, counts: dict | None = None):
    """Return a redacted deep copy + counts of what was removed."""
    counts = {} if counts is None else counts
    fields = {f.lower() for f in (fields or [])}
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k.lower() in fields and v is not None:
                counts[f"field:{k}"] = counts.get(f"field:{k}", 0) + 1
                out[k] = f"[REDACTED:{k}]"
            else:
                out[k] = strip(v, list(fields), counts)
        return out
    if isinstance(obj, list):
        return [strip(v, list(fields), counts) for v in obj]
    if isinstance(obj, str):
        s = obj
        for name, pat in PII_PATTERNS.items():
            s, n = pat.subn(f"[REDACTED:{name}]", s)
            if n:
                counts[name] = counts.get(name, 0) + n
        return s
    return obj


def check_output(text: str) -> tuple[str, dict]:
    counts = {}
    clean = strip(text, [], counts)
    return clean, counts


def scan_injection(obj) -> list[str]:
    hits = []

    def walk(v, path):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{path}.{k}" if path else k)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{path}[{i}]")
        elif isinstance(v, str):
            for p in INJECTION_PATTERNS:
                m = p.search(v)
                if m:
                    hits.append(f"{path}: “{m.group(0)}”")
    walk(obj, "")
    return hits
