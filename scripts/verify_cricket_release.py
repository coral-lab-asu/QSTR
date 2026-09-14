"""Verify the versioned cricket data release and rebuild its checksum manifest."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data"
TABLE_ROOT = DATA_ROOT / "Cricket_tables"
SEED_PATH = DATA_ROOT / "data_manual_template" / "template_q_param_cricket_pk.py"
DIVERSITY_PATH = DATA_ROOT / "data_manual_template" / "cricket_sql_question_templates_1000.csv"
GENERATED_PATH = DATA_ROOT / "data_final" / "test_generated_sql_nl.json"
GROUND_TRUTH_PATH = DATA_ROOT / "data_final" / "test_generated_sql_nl.ground_truth.json"
PIPELINE_SEED_PATH = REPO_ROOT / "pipelines" / "cmt2" / "template_q_param_cricket_pk.py"
MANIFEST_PATH = DATA_ROOT / "MANIFEST.sha256"

EXPECTED_TABLES = 638
EXPECTED_TABLE_ROWS = 150_666
EXPECTED_SEEDS = 121
EXPECTED_DIVERSITY_ROWS = 1_000
EXPECTED_GENERATED = 4_256
EXPECTED_ENRICHED = 4_239
EXPECTED_UNRESOLVED = 17
EXPECTED_COLUMNS = (
    "raw_data",
    "overs",
    "runs",
    "team_runs",
    "commentary",
    "bowler",
    "batsman",
    "batsman_runs",
    "batsman_fours",
    "batsman_sixes",
    "batsman_bowls_faced",
    "bowler_bowls_done",
    "bowler_runs_given",
    "bowler_wickets",
    "dismissal",
    "runs_given_bool",
)
REQUIRED_QUERY_FIELDS = {
    "intent",
    "structure",
    "sql",
    "description",
    "item_id",
    "question",
    "template_id",
    "round_idx",
}


def release_files() -> list[Path]:
    """Return exactly the files covered by the release checksum manifest."""
    tables = sorted(TABLE_ROOT.glob("*.csv"))
    return tables + [SEED_PATH, DIVERSITY_PATH, GENERATED_PATH, GROUND_TRUTH_PATH]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest() -> None:
    lines = [f"{sha256(path)}  {path.relative_to(REPO_ROOT).as_posix()}" for path in release_files()]
    MANIFEST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_seed_templates(path: Path) -> list[dict]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "question_templates" for target in node.targets):
            value = ast.literal_eval(node.value)
            if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
                raise ValueError("question_templates must be a list of objects")
            return value
    raise ValueError("question_templates assignment not found")


def verify_manifest(errors: list[str]) -> None:
    expected_paths = {path.relative_to(REPO_ROOT).as_posix(): path for path in release_files()}
    recorded: dict[str, str] = {}
    for line_number, line in enumerate(MANIFEST_PATH.read_text(encoding="utf-8").splitlines(), 1):
        try:
            digest, relative_path = line.split("  ", 1)
        except ValueError:
            errors.append(f"manifest line {line_number} is malformed")
            continue
        recorded[relative_path] = digest

    if set(recorded) != set(expected_paths):
        errors.append("manifest file set does not match the cricket release")
    for relative_path, path in expected_paths.items():
        if recorded.get(relative_path) != sha256(path):
            errors.append(f"checksum mismatch: {relative_path}")


def verify() -> list[str]:
    errors: list[str] = []
    required = [SEED_PATH, DIVERSITY_PATH, GENERATED_PATH, GROUND_TRUTH_PATH, MANIFEST_PATH]
    missing = [path for path in required if not path.is_file()]
    if missing:
        return [f"missing required file: {path.relative_to(REPO_ROOT)}" for path in missing]

    table_paths = sorted(TABLE_ROOT.glob("*.csv"))
    if len(table_paths) != EXPECTED_TABLES:
        errors.append(f"expected {EXPECTED_TABLES} tables, found {len(table_paths)}")

    total_rows = 0
    for path in table_paths:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = tuple(next(reader, ()))
            if header != EXPECTED_COLUMNS:
                errors.append(f"unexpected table schema: {path.relative_to(REPO_ROOT)}")
            total_rows += sum(1 for _ in reader)
    if total_rows != EXPECTED_TABLE_ROWS:
        errors.append(f"expected {EXPECTED_TABLE_ROWS} table rows, found {total_rows}")

    seeds = load_seed_templates(SEED_PATH)
    if len(seeds) != EXPECTED_SEEDS:
        errors.append(f"expected {EXPECTED_SEEDS} seed templates, found {len(seeds)}")
    if SEED_PATH.read_bytes() != PIPELINE_SEED_PATH.read_bytes():
        errors.append("data seed file differs from the CMT2 pipeline seed file")

    with DIVERSITY_PATH.open(encoding="utf-8-sig", newline="") as handle:
        diversity = list(csv.DictReader(handle))
    if len(diversity) != EXPECTED_DIVERSITY_ROWS:
        errors.append(f"expected {EXPECTED_DIVERSITY_ROWS} diversity rows, found {len(diversity)}")

    generated = json.loads(GENERATED_PATH.read_text(encoding="utf-8"))
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    if not isinstance(generated, list) or len(generated) != EXPECTED_GENERATED:
        errors.append(f"expected {EXPECTED_GENERATED} generated queries")
        generated = []
    if not isinstance(ground_truth, list) or len(ground_truth) != EXPECTED_GENERATED:
        errors.append(f"expected {EXPECTED_GENERATED} ground-truth records")
        ground_truth = []

    for index, record in enumerate(generated):
        missing_fields = REQUIRED_QUERY_FIELDS - set(record)
        if missing_fields:
            errors.append(f"generated record {index} is missing {sorted(missing_fields)}")

    if generated and ground_truth:
        generated_ids = [record.get("item_id") for record in generated]
        ground_truth_ids = [record.get("item_id") for record in ground_truth]
        if generated_ids != ground_truth_ids:
            errors.append("generated and ground-truth record order/item IDs differ")

        enriched = 0
        unresolved = 0
        for index, record in enumerate(ground_truth):
            match_path = record.get("match_path")
            result = record.get("ground_truth_table")
            if match_path and result is not None:
                enriched += 1
                source = REPO_ROOT / str(match_path)
                if not source.is_file():
                    errors.append(f"ground-truth record {index} references a missing table: {match_path}")
            elif not match_path and result is None:
                unresolved += 1
            else:
                errors.append(f"ground-truth record {index} has partial provenance")
        if enriched != EXPECTED_ENRICHED or unresolved != EXPECTED_UNRESOLVED:
            errors.append(
                f"expected {EXPECTED_ENRICHED} enriched and {EXPECTED_UNRESOLVED} unresolved records; "
                f"found {enriched} and {unresolved}"
            )

    verify_manifest(errors)
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true", help="Rebuild data/MANIFEST.sha256 before checking.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.write_manifest:
        write_manifest()
        print(f"Wrote {MANIFEST_PATH.relative_to(REPO_ROOT)} with {len(release_files())} entries.")
    errors = verify()
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(
        "Cricket release verified: "
        f"{EXPECTED_TABLES} tables, {EXPECTED_TABLE_ROWS} rows, {EXPECTED_SEEDS} seeds, "
        f"{EXPECTED_GENERATED} generated queries ({EXPECTED_ENRICHED} enriched, "
        f"{EXPECTED_UNRESOLVED} unresolved)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
