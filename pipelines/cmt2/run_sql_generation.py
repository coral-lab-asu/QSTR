"""
Entry point to run the CrewAI SQL-generation pipeline for a single CSV.

Usage (from project root, in env `genai` with dependencies installed):

    python run_sql_generation.py --csv Cricket_tables/game_XXXX.csv --output out.json

This will:
  1. Build the crew defined in `sql_crew_agents.py`.
  2. Run the 4-step pipeline (generate SQL -> NL -> validate -> fix).
  3. Print the final JSON to stdout and optionally save it to `--output`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the CrewAI SQL generation & validation pipeline for one CSV."
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to the CSV file to treat as table 'df' (e.g., Cricket_tables/game_XXXX.csv).",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Optional path to save the final JSON results.",
    )
    parser.add_argument(
        "--progress",
        help="Optional path to write incremental progress JSON after each template.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        from .sql_crew_agents import kickoff_for_csv
    except ImportError:  # Supports direct execution from the CMT2 directory.
        from sql_crew_agents import kickoff_for_csv

    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    print(f"[run_sql_generation] Using CSV: {csv_path}")
    result = kickoff_for_csv(
        str(csv_path),
        progress_json_path=args.progress,
    )

    print("\n=== FINAL RESULT (JSON) ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[run_sql_generation] Saved results to {out_path}")


if __name__ == "__main__":
    main()
