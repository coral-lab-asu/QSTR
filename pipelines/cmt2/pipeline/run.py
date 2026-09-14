"""CLI for the CMT2 generation -> validation -> deduplication flow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from .dataset_pipeline import deduplicate_records, load_records, validate_records, write_records
except ImportError:  # Supports `python pipeline/run.py` from the CMT2 root.
    from dataset_pipeline import deduplicate_records, load_records, validate_records, write_records


def _add_generation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--templates", nargs="+", default=["template_q_param_cricket_pk.py"])
    parser.add_argument("--matches-glob", default="Cricket_tables/*.csv")
    parser.add_argument("--out-dir", default="output/dataset_runs/cmt2")
    parser.add_argument("--max-matches", type=int, default=10)
    parser.add_argument("--total-examples", type=int, default=5000)
    parser.add_argument("--samples-per-template-per-match", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--context-max-chars", type=int, default=0)
    parser.add_argument("--answer-max-rows", type=int, default=0)
    parser.add_argument("--drop-zeroish", action="store_true")
    parser.add_argument("--write-analysis-jsonls", action="store_true")
    parser.add_argument("--roi-stratify", action="store_true")
    parser.add_argument("--roi-bucket-mode", choices=["random", "round_robin"], default="random")


def _generate_template_dataset(args: argparse.Namespace) -> Dict[str, Any]:
    from generate_questions import PipelineConfig, generate_dataset

    config = PipelineConfig(
        templates_paths=args.templates,
        matches_glob=args.matches_glob,
        output_dir=args.out_dir,
        max_matches=args.max_matches,
        total_examples=args.total_examples,
        samples_per_template_per_match=args.samples_per_template_per_match,
        seed=args.seed,
        context_max_chars=args.context_max_chars,
        answer_max_rows=args.answer_max_rows,
        drop_zeroish=args.drop_zeroish,
        write_analysis_jsonls=args.write_analysis_jsonls,
        roi_stratify=args.roi_stratify,
        roi_bucket_mode=args.roi_bucket_mode,
    )
    return generate_dataset(config)


def _write_validation_report(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate answer-grounded JSONL datasets from templates.")
    _add_generation_args(generate)

    validate = subparsers.add_parser("validate", help="Execute SQL and compare stored answers.")
    validate.add_argument("--input", required=True)
    validate.add_argument("--csv", help="Fallback CSV when records do not contain match_path/csv_path.")
    validate.add_argument("--report", required=True)

    deduplicate = subparsers.add_parser("deduplicate", help="Remove duplicate source/result records.")
    deduplicate.add_argument("--input", required=True)
    deduplicate.add_argument("--output", required=True)
    deduplicate.add_argument("--removed-output", required=True)

    run = subparsers.add_parser("run", help="Run generation, validation, and deduplication together.")
    _add_generation_args(run)

    args = parser.parse_args()
    if args.command == "generate":
        print(json.dumps(_generate_template_dataset(args), indent=2, ensure_ascii=False))
        return

    if args.command == "validate":
        records, _ = load_records(args.input)
        report = validate_records(records, default_csv=args.csv)
        _write_validation_report(Path(args.report), report)
        print(json.dumps({k: report[k] for k in ("total_records", "valid_records", "invalid_records")}, indent=2))
        return

    if args.command == "deduplicate":
        records, envelope = load_records(args.input)
        kept, removed = deduplicate_records(records)
        write_records(args.output, kept, envelope=envelope)
        Path(args.removed_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.removed_output).write_text(json.dumps(removed, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"input": len(records), "kept": len(kept), "removed": len(removed)}, indent=2))
        return

    generated = _generate_template_dataset(args)
    dataset_path = Path(generated["dataset_path_no_overs"])
    records, envelope = load_records(dataset_path)
    report = validate_records(records)
    report_path = dataset_path.with_name("validation.no_overs.json")
    _write_validation_report(report_path, report)
    kept, removed = deduplicate_records(records)
    dedup_path = dataset_path.with_name("dataset.no_overs.deduped.jsonl")
    removed_path = dataset_path.with_name("dataset.no_overs.removed.json")
    write_records(dedup_path, kept, envelope=envelope)
    removed_path.write_text(json.dumps(removed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "generated": generated,
        "validation": str(report_path),
        "deduplicated": str(dedup_path),
        "removed": str(removed_path),
        "valid_records": report["valid_records"],
        "invalid_records": report["invalid_records"],
        "kept_records": len(kept),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
