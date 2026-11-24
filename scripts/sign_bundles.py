"""Sign every bundle under bundles/ with the platform key (the central authority's job).
Only manifest.yaml is rewritten (hash + signature); the artifacts are left untouched.

Usage: python scripts/sign_bundles.py [domain ...]"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ariax.core.bundle import Signer, content_hash, load_dir, validate  # noqa: E402

signer = Signer(ROOT / "data" / ".signing_key")
BUNDLES = ROOT / "examples" / "bundles"
targets = sys.argv[1:] or sorted(p.name for p in BUNDLES.iterdir() if p.is_dir())
failed = False
for name in targets:
    path = BUNDLES / name
    b = load_dir(path)
    digest = content_hash(b)
    b["manifest"]["hash"] = digest
    b["manifest"]["signature"] = signer.sign(digest)
    errors = [] if name.startswith("_") else validate(b)
    (path / "manifest.yaml").write_text(yaml.safe_dump(b["manifest"], sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"signed {name:<12} {digest[:16]}  {'OK' if not errors else f'{len(errors)} validation error(s)'}")
    for e in errors:
        print("   -", e)
    failed |= bool(errors)
sys.exit(1 if failed else 0)
