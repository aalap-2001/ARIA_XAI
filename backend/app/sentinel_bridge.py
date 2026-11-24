"""Sentinel rails applied to everything sent to a model provider."""
from ariax.sentinel import rails

ALWAYS = ("ssn", "card", "iban")
CONTACT = ("email", "phone")


def redact(obj, contact: bool = True, counts: dict | None = None):
    """Strip identifiers before data leaves for an AI provider. Government/financial ids always;
    email and phone unless the organisation turned that off."""
    counts = {} if counts is None else counts
    names = ALWAYS + (CONTACT if contact else ())
    if isinstance(obj, dict):
        return {k: redact(v, contact, counts) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v, contact, counts) for v in obj]
    if isinstance(obj, str):
        s = obj
        for n in names:
            s, k = rails.PII_PATTERNS[n].subn(f"[REDACTED:{n}]", s)
            if k:
                counts[n] = counts.get(n, 0) + k
        return s
    return obj


def injection_flags(obj) -> list[str]:
    return rails.scan_injection(obj)
