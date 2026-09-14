"""Common benchmark input contract; fail before sending incomplete prompts."""
import json
from pathlib import Path


def read_dataset(path):
    source = Path(path)
    hint = "Prepare inputs with: python -m scripts.prepare_benchmark"
    if not source.is_file():
        raise FileNotFoundError(f"Benchmark dataset missing: {source}. {hint}")
    with source.open(encoding="utf-8") as handle:
        if source.suffix == ".jsonl":
            rows = [json.loads(line) for line in handle if line.strip()]
        else:
            rows = json.load(handle)
            if isinstance(rows, dict):
                rows = rows.get("records")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"Expected a nonempty benchmark list or JSONL. {hint}")
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"Benchmark row {index} is not an object. {hint}")
        context = row.get("context_full_with_overs") or row.get("context") or row.get("context_full")
        answer = row.get("answer")
        if not context or not row.get("question") or not isinstance(answer, dict) or not answer.get("columns") or not isinstance(answer.get("rows"), list):
            raise ValueError(f"Benchmark row {index} lacks context, question, or answer table. {hint}")
        row["context"] = context
        row.setdefault("sample_id", index)
        row.setdefault("record_id", f"benchmark-{index}")
        if row["record_id"] in seen:
            raise ValueError(f"Duplicate benchmark record_id at row {index}. {hint}")
        seen.add(row["record_id"])
    return rows
