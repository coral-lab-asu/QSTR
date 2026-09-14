"""Prepare validated, uniquely identified commentary records for benchmarks."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pipelines.cmt2.pipeline.dataset_pipeline import load_records, validate_records, write_records

ROOT = Path(__file__).resolve().parents[1]


def prepare(input_path: Path, output: Path) -> dict:
    import pandas as pd
    from pipelines.cmt2.generate_questions import build_context_from_df

    records, _ = load_records(input_path)
    candidates, excluded = [], []
    contexts = {}
    for index, original in enumerate(records):
        row = dict(original)
        answer = row.get("answer") or row.get("ground_truth_table")
        source = row.get("match_path") or row.get("csv_path")
        if not isinstance(answer, dict) or not source or not row.get("question"):
            excluded.append({"index": index, "error": "missing answer, source, or question"})
            continue
        path = Path(source)
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file():
            excluded.append({"index": index, "error": "source table missing"})
            continue
        if str(path) not in contexts:
            contexts[str(path)] = build_context_from_df(
                pd.read_csv(path), commentary_col="commentary", overs_col="overs",
                include_overs=True, max_chars=0,
            )
        context = contexts[str(path)]
        if not context.strip():
            excluded.append({"index": index, "error": "empty commentary"})
            continue
        # Full commentary is an explicit benchmark choice, independent of
        # approximate supporting-row attribution in generated datasets.
        row.update(answer=answer, context=context, context_full_with_overs=context,
                   answer_rows=len(answer.get("rows", [])), sample_id=index,
                   record_id=f"benchmark-{index}", source_record_id=original.get("record_id"))
        row["match_path"] = str(path)
        candidates.append(row)
    report = validate_records(candidates)
    kept = []
    for row, detail in zip(candidates, report["records"]):
        if detail["ok"] and detail.get("answer_checked"):
            path = Path(row["match_path"])
            if path.is_relative_to(ROOT):
                row["match_path"] = path.relative_to(ROOT).as_posix()
            kept.append(row)
        else:
            excluded.append({"index": row["sample_id"], "error": detail.get("error")})
    if not kept:
        raise ValueError("No valid benchmark records; inspect source answers and CSV paths.")
    write_records(output, kept)
    manifest = {"input": str(input_path), "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                "output": str(output), "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "context_policy": "full commentary with overs", "input_records": len(records),
                "accepted": len(kept), "excluded": excluded}
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/data_final/test_generated_sql_nl.ground_truth.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/runs/benchmark/dataset.jsonl")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("Input and output must differ")
    result = prepare(args.input, args.output)
    print(json.dumps({"accepted": result["accepted"], "excluded": len(result["excluded"]), "output": result["output"]}))


if __name__ == "__main__":
    main()
