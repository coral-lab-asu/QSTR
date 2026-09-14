"""
Entry point for deduplicated, resumable SQL generation.

This runner:
- Uses sql_crew_agents_dedup.kickoff_until_target
- Supports resume
- Scales to large targets (e.g. 5k)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deduplicated SQL+NL generation with resume support."
    )

    parser.add_argument(
        "--csv",
        required=True,
        help="Path to the CSV file to treat as table 'df'.",
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Optional path to save the final JSON results.",
    )

    parser.add_argument(
        "--progress",
        required=True,
        help="Path to progress JSON (used for resume + dedupe).",
    )

    parser.add_argument(
        "--target",
        type=int,
        default=5000,
        help="Target number of unique SQL/NL items to generate (default: 5000).",
    )

    parser.add_argument(
        "--rounds-per-template",
        type=int,
        default=10,
        help="Number of rounds per base template (default: 10).",
    )

    parser.add_argument(
        "--diversity-csv",
        help="CSV path for diversity template bank (1000-bank).",
    )

    parser.add_argument(
        "--diversity-k",
        type=int,
        default=4,
        help="How many diversity templates to inject per round (default: 4).",
    )

    parser.add_argument(
        "--resume-from-sql-json",
        help="Optional JSON file containing previous SQL outputs to seed dedupe.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        from .sql_crew_agents_dedup import kickoff_until_target
    except ImportError:  # Supports direct execution from the CMT2 directory.
        from sql_crew_agents_dedup import kickoff_until_target

    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    print(f"[run_sql_generation_dedup] Using CSV: {csv_path}")
    print(f"[run_sql_generation_dedup] Target unique items: {args.target}")
    print(f"[run_sql_generation_dedup] Progress file: {args.progress}")

    result = kickoff_until_target(
        csv_path=str(csv_path),
        target_unique=args.target,
        progress_json_path=args.progress,
        rounds_per_template=args.rounds_per_template,
        diversity_csv_path=args.diversity_csv,
        diversity_k=args.diversity_k,
        resume_from_sql_json_path=args.resume_from_sql_json,
    )

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[run_sql_generation_dedup] Saved results to {out_path}")

    print("\n=== FINAL SUMMARY ===")
    print(json.dumps(
        {
            "total_generated": len(result.get("final", [])),
            "total_failed": len(result.get("failed", [])),
            "registry_size": result.get("registry_size"),
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()


# python run_sql_generation_dedup.py \
#   --csv "Cricket_tables/Ball by Ball Commentary & Live Score - AFG vs AUS, 10th Match, Group B.csv" \
#   --output test_generated_sql_nl_final_5k.json \
#   --progress test_generated_sql_nl_progress_5k.json \
#   --target 5000 \
#   --rounds-per-template 12 \
#   --diversity-csv cricket_sql_question_templates_1000_with_sql.csv \
#   --diversity-k 4
#   --resume-from-sql-json test_generated_sql_nl_progress_5k_4.json
