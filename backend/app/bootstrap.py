"""Ensure repo packages (debating, sim_chat) are importable."""

from __future__ import annotations

import sys
from pathlib import Path


def setup_paths() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    src = repo_root / "src"
    paths = [str(src), str(repo_root)]
    for path in paths:
        if path not in sys.path:
            sys.path.insert(0, path)
    return repo_root
