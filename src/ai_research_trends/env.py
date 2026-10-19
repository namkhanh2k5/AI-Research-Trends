"""Environment loading with a minimal fallback for bootstrap environments."""

from __future__ import annotations

import os
from pathlib import Path


def load_project_env(path: str | Path = ".env") -> None:
    """Load `.env` via python-dotenv, or parse basic KEY=VALUE lines if unavailable."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        env_path = Path(path)
        if not env_path.exists():
            return
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    else:
        load_dotenv(dotenv_path=path)
