import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ariax.runtime import Platform  # noqa: E402


@pytest.fixture()
def platform(tmp_path):
    """A fresh platform per test, signed with the same key as the shipped bundles."""
    key = ROOT / "data" / ".signing_key"
    if key.exists():
        shutil.copy(key, tmp_path / ".signing_key")
    p = Platform(data_dir=tmp_path)
    assert not p.bundles.rejected, p.bundles.rejected
    return p
