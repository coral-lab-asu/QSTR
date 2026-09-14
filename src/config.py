"""Shared environment loading for QSTR Python entry points."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_project_env() -> bool:
    """Load QSTR's untracked .env when python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    env_root = REPO_ROOT if (REPO_ROOT / "pyproject.toml").exists() else Path.cwd()
    return bool(load_dotenv(env_root / ".env", override=False))
