"""
Shared tools for the SQL-generation Crew:

- Load SQL+NL templates from `template_q_param_cricket_pk.py`
- Discover available CSV tables (cricket by default)
- Inspect table schema and preview data
- Run SQL against a pandas DataFrame via duckdb

These are plain Python utilities; CrewAI tool-wrappers are defined in
`sql_crew_agents.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import duckdb
import pandas as pd

# ---------------------------------------------------------------------------
# Paths / configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent

# Template file with question_templates as in template_q_param_cricket_pk.py
TEMPLATE_FILE = PROJECT_ROOT / "data" / "data_manual_template" / "template_q_param_cricket_pk.py"

# Default directory of cricket CSV tables
CRICKET_TABLE_DIR = PROJECT_ROOT / "data" / "Cricket_tables"


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def load_templates() -> List[Dict[str, Any]]:
    """
    Load SQL/NL templates from TEMPLATE_FILE.

    Expected structure (from template_q_param_cricket_pk.py):
        question_templates = [
            {
                "id": 1,
                "question": "...",
                "query": "... {table_name} ...",
                "exp": "...",
                "variables": [...],
                "paraphrases": [...],
                "primary_key": [...]
            },
            ...
        ]
    """
    ns: Dict[str, Any] = {}
    if not TEMPLATE_FILE.exists():
        raise FileNotFoundError(f"Template file not found: {TEMPLATE_FILE}")

    code = TEMPLATE_FILE.read_text(encoding="utf-8")
    exec(code, ns, ns)  # noqa: S102 - executed in local, trusted repo file

    templates = ns.get("question_templates") or ns.get("question_cricket") or []
    if not isinstance(templates, list):
        raise ValueError(
            f"Expected `question_templates` to be a list in {TEMPLATE_FILE}, "
            f"got {type(templates)}"
        )
    return templates


def list_csvs(base_dir: Path | None = None) -> List[Path]:
    """
    Return all CSV files under the given directory (recursively).
    Defaults to CRICKET_TABLE_DIR.
    """
    root = base_dir or CRICKET_TABLE_DIR
    if not root.exists():
        raise FileNotFoundError(f"CSV base directory does not exist: {root}")

    return sorted(root.rglob("*.csv"))


def load_df(csv_path: Path) -> pd.DataFrame:
    """Load a CSV into a pandas DataFrame."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    return pd.read_csv(csv_path)


def sample_table_schema(csv_path: Path, n_rows: int = 5) -> Dict[str, Any]:
    """
    Return a small schema+preview for the given CSV.

    Structure:
        {
            "path": "...",
            "columns": [{"name": ..., "dtype": ...}, ...],
            "preview": [row_dict, ...]
        }
    """
    df = load_df(csv_path)
    df.drop(columns=["raw_data","commentary","dismissal","runs_given_bool","runs"], inplace=True)
    return {
        "columns": [{"name": c, "dtype": str(df[c].dtype)} for c in df.columns],
        "preview": df.sample(n_rows).to_dict(orient="records"),
    }


def run_sql_on_df(sql: str, csv_path: Path) -> Dict[str, Any]:
    """
    Register the CSV as table `df` in duckdb and execute the SQL.

    Returns:
        {
            "ok": bool,
            "error": Optional[str],
            "row_count": Optional[int],
            "columns": Optional[List[str]]
        }
    """
    df = load_df(csv_path)

    con = duckdb.connect(database=":memory:")
    con.register("df", df)

    result: Dict[str, Any] = {
        "ok": True,
        "error": None,
        "row_count": None,
        "columns": None,
    }

    try:
        out = con.execute(sql).fetchdf()
        result["row_count"] = len(out)
        result["columns"] = list(out.columns)
        #result["sample_rows"] = out.head(1).to_dict(orient="records")
        print(result)
    except Exception as e:  # noqa: BLE001 - we want the message
        result["ok"] = False
        result["error"] = str(e)
    finally:
        con.close()

    return result




def pretty_json(obj: Any, max_chars: int | None = None) -> str:
    """Return a pretty JSON string, optionally truncated."""
    s = json.dumps(obj, indent=2, ensure_ascii=False)
    if max_chars is not None and len(s) > max_chars:
        return s[:max_chars] + "\n... (truncated)"
    return s


__all__ = [
    "TEMPLATE_FILE",
    "CRICKET_TABLE_DIR",
    "load_templates",
    "list_csvs",
    "load_df",
    "sample_table_schema",
    "run_sql_on_df",
    "pretty_json",
]

