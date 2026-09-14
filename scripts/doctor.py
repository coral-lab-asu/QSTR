"""Check whether a QSTR checkout is ready for its documented workflows."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_MODULES = {
    "duckdb": "duckdb",
    "numpy": "numpy",
    "pandas": "pandas",
    "rapidfuzz": "rapidfuzz",
    "scipy": "scipy",
    "sqlglot": "sqlglot",
    "tqdm": "tqdm",
}
LLM_MODULES = {
    "CrewAI": "crewai",
    "Google Generative AI": "google.generativeai",
    "Google Gen AI": "google.genai",
    "OpenAI": "openai",
}
SYNTHETIC_MODULES = {
    "Hugging Face datasets": "datasets",
    "python-dotenv": "dotenv",
}


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_root = REPO_ROOT if (REPO_ROOT / "pyproject.toml").exists() else Path.cwd()
    load_dotenv(env_root / ".env", override=False)


def _available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _check_modules(title: str, modules: dict[str, str], *, required: bool) -> int:
    missing = 0
    print(f"\n{title}")
    for label, module in modules.items():
        present = _available(module)
        print(f"  {'OK' if present else 'MISSING':7} {label} ({module})")
        if required and not present:
            missing += 1
    return missing


def _check_files(paths: Iterable[Path]) -> int:
    missing = 0
    print("\nRepository fixtures")
    for path in paths:
        present = path.exists()
        print(f"  {'OK' if present else 'MISSING':7} {path.relative_to(REPO_ROOT)}")
        if not present:
            missing += 1
    return missing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-llm", action="store_true", help="Fail when hosted-LLM dependencies are missing.")
    parser.add_argument(
        "--require-synthetic",
        action="store_true",
        help="Fail when synthetic-data download/inference dependencies are missing.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    _load_env()
    print(f"QSTR root: {REPO_ROOT}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")

    failures = 0
    if sys.version_info < (3, 10):
        print("FAIL: QSTR requires Python 3.10 or newer.")
        failures += 1

    failures += _check_modules("Core dependencies", CORE_MODULES, required=True)
    failures += _check_modules("Hosted-LLM dependencies", LLM_MODULES, required=args.require_llm)
    failures += _check_modules("Synthetic-data dependencies", SYNTHETIC_MODULES, required=args.require_synthetic)
    fixture_paths = [
        REPO_ROOT / "pipelines/cmt2/examples/smoke_match.csv",
        REPO_ROOT / "pipelines/cmt2/examples/smoke_templates.py",
    ]
    if (REPO_ROOT / "pyproject.toml").exists():
        fixture_paths.insert(0, REPO_ROOT / ".env.example")
    failures += _check_files(fixture_paths)

    print("\nCredentials (presence only; values are never displayed)")
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "DEEPINFRA_API_KEY", "HF_TOKEN"):
        print(f"  {'SET' if os.getenv(name) else 'unset':7} {name}")

    if failures:
        print(f"\nQSTR is not ready: {failures} required check(s) failed.")
        return 1
    print("\nQSTR core environment is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
