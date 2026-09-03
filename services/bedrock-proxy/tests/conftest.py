"""Shared pytest bootstrap for the standalone Host Agent package."""
from __future__ import annotations

import sys
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))
