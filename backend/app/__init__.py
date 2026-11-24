"""Aria XAI product backend. The engine (`ariax/`) lives one level up and is imported directly."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
