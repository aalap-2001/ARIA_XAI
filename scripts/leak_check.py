"""CI rule from day one (§01, §08 layer 5): no file under ariax/ may contain a domain noun,
and the engine may not import raw HTTP or database-driver libraries outside the connector layer.

Usage: python scripts/leak_check.py   (exit 1 on any hit)"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "ariax"
PRODUCT = ROOT / "backend" / "app"   # the product must be just as domain-agnostic as the engine

# Nouns from every bundle we ship plus common ones. If the engine names one, a domain has leaked in.
DOMAIN_NOUNS = ["claim", "payer", "cpt", "patient", "appeal", "denial", "loan", "applicant", "bureau", "underwrit",
                "refund", "sku", "shopper", "invoice", "contract", "portfolio", "mortgage", "diagnosis", "aetna"]
RAW_IO = [r"^\s*import (requests|httpx|urllib3|psycopg2?|pymysql)\b", r"^\s*from (requests|httpx|psycopg2?|pymysql)\b"]
ALLOW_RAW_IO = {"connectors", "llm"}  # the connector and model-provider layers are the only places transports live
ALLOW_RAW_IO_FILES = {"datasources.py", "decisions.py"}  # product data connectors; governed webhook egress


def scan() -> list[str]:
    hits = []
    noun_re = re.compile(r"\b(" + "|".join(DOMAIN_NOUNS) + r")", re.I)
    for f in sorted([*ENGINE.rglob("*"), *PRODUCT.rglob("*")]):
        if f.suffix not in (".py", ".sql") or "__pycache__" in f.parts:
            continue
        rel = f.relative_to(ROOT).as_posix()
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            m = noun_re.search(line)
            if m:
                hits.append(f"{rel}:{i} domain noun '{m.group(1)}'")
            if f.parent.name not in ALLOW_RAW_IO and f.name not in ALLOW_RAW_IO_FILES and any(re.search(p, line) for p in RAW_IO):
                hits.append(f"{rel}:{i} raw I/O import outside the connector layer")
    return hits


if __name__ == "__main__":
    found = scan()
    for h in found:
        print(h)
    print(f"{len(found)} leak(s)" if found else "OK, engine contains no domain vocabulary")
    sys.exit(1 if found else 0)
