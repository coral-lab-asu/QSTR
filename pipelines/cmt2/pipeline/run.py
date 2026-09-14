"""CLI for the CMT2 generation -> validation -> deduplication flow."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


CMT2_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(CMT2_ROOT) not in sys.path:
    sys.path.insert(0, str(CMT2_ROOT))

try:
    from .dataset_pipeline import deduplicate_records, load_records, validate_records, write_records
except ImportError:  # Supports `python pipeline/run.py` from the CMT2 directory.
    from dataset_pipeline import deduplicate_records, load_records, validate_records, write_records


def _add_generation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--templates",
        nargs="+",
        default=[str(CMT2_ROOT / "template_q_param_cricket_pk.py")],
        help="One or more Python/JSON template files.",
    )
    parser.add_argument(
        "--matches-glob",
        default=str(CMT2_ROOT / "Cricket_tables/*.csv"),
        help="Glob for source match CSV files.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(CMT2_ROOT / "output/dataset_runs/cmt2"),
        help="Directory for generated datasets and reports.",
    )
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
    try:
        from ..generate_questions import PipelineConfig, generate_dataset
    except ImportError:  # Supports direct script execution from the CMT2 directory.
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
    generated = generate_dataset(config)
    if not generated.get("num_examples"):
        raise RuntimeError(
            "Generation produced zero records. Check errors.json, template compatibility, and the source CSV schema."
        )
    return generated


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def _git_dirty() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def _write_manifest(
    path: Path,
    *,
    args: argparse.Namespace,
    generated: Dict[str, Any],
    report: Dict[str, Any],
    deduplicated_path: Path,
    invalid_path: Path,
    removed_path: Path,
) -> None:
    _write_json(
        path,
        {
            "schema_version": 1,
            "pipeline": "qstr.cmt2",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "qstr_commit": _git_commit(),
            "qstr_worktree_dirty": _git_dirty(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "configuration": {
                key: value
                for key, value in vars(args).items()
                if key not in {"command", "allow_invalid"}
            },
            "outputs": {
                "generated": generated,
                "validation": {
                    "total_records": report["total_records"],
                    "valid_records": report["valid_records"],
                    "invalid_records": report["invalid_records"],
                },
                "deduplicated": str(deduplicated_path),
                "invalid": str(invalid_path),
                "removed_duplicates": str(removed_path),
            },
        },
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate answer-grounded JSONL datasets from templates.")
    _add_generation_args(generate)

    validate = subparsers.add_parser("validate", help="Execute read-only SQL and compare stored answers.")
    validate.add_argument("--input", required=True)
    validate.add_argument("--csv", help="Fallback CSV when records do not contain match_path/csv_path.")
    validate.add_argument("--report", required=True)
    validate.add_argument(
        "--allow-invalid",
        action="store_true",
        help="Return success even when one or more records fail validation.",
    )

    deduplicate = subparsers.add_parser("deduplicate", help="Remove duplicate source/result records.")
    deduplicate.add_argument("--input", required=True)
    deduplicate.add_argument("--output", required=True)
    deduplicate.add_argument("--removed-output", required=True)

    run = subparsers.add_parser("run", help="Run generation, validation, and deduplication together.")
    _add_generation_args(run)
    run.add_argument(
        "--allow-invalid",
        action="store_true",
        help="Return success after writing reports even when generated records fail validation.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "generate":
        print(json.dumps(_generate_template_dataset(args), indent=2, ensure_ascii=False))
        return 0

    if args.command == "validate":
        records, _ = load_records(args.input)
        report = validate_records(records, default_csv=args.csv)
        report["input_path"] = str(Path(args.input))
        _write_json(Path(args.report), report)
        print(json.dumps({k: report[k] for k in ("total_records", "valid_records", "invalid_records")}, indent=2))
        return 1 if report["invalid_records"] and not args.allow_invalid else 0

    if args.command == "deduplicate":
        records, envelope = load_records(args.input)
        kept, removed = deduplicate_records(records)
        write_records(args.output, kept, envelope=envelope)
        _write_json(Path(args.removed_output), removed)
        print(json.dumps({"input": len(records), "kept": len(kept), "removed": len(removed)}, indent=2))
        return 0

    generated = _generate_template_dataset(args)
    dataset_path = Path(generated["dataset_path_no_overs"])
    records, envelope = load_records(dataset_path)
    if not records:
        raise RuntimeError(f"Generated dataset is empty: {dataset_path}")

    report = validate_records(records)
    report["input_path"] = str(dataset_path)
    report_path = dataset_path.with_name("validation.no_overs.json")
    _write_json(report_path, report)

    valid_indices = {detail["index"] for detail in report["records"] if detail.get("ok")}
    valid_records = [record for index, record in enumerate(records) if index in valid_indices]
    invalid_entries = [
        {"validation": detail, "record": records[detail["index"]]}
        for detail in report["records"]
        if not detail.get("ok")
    ]

    kept, removed = deduplicate_records(valid_records)
    dedup_path = dataset_path.with_name("dataset.no_overs.deduped.jsonl")
    invalid_path = dataset_path.with_name("dataset.no_overs.invalid.json")
    removed_path = dataset_path.with_name("dataset.no_overs.removed.json")
    manifest_path = dataset_path.with_name("run_manifest.json")
    write_records(dedup_path, kept, envelope=envelope)
    _write_json(invalid_path, invalid_entries)
    _write_json(removed_path, removed)
    _write_manifest(
        manifest_path,
        args=args,
        generated=generated,
        report=report,
        deduplicated_path=dedup_path,
        invalid_path=invalid_path,
        removed_path=removed_path,
    )

    print(
        json.dumps(
            {
                "generated": generated,
                "validation": str(report_path),
                "deduplicated": str(dedup_path),
                "invalid": str(invalid_path),
                "removed": str(removed_path),
                "manifest": str(manifest_path),
                "valid_records": report["valid_records"],
                "invalid_records": report["invalid_records"],
                "kept_records": len(kept),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 1 if report["invalid_records"] and not args.allow_invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
