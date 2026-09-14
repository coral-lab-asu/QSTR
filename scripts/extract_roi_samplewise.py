#!/usr/bin/env python3
"""Extract question, gold_sql, gold_answer, and table dimensions from roi_suite.samplewise.json."""

import json
import csv
from pathlib import Path

INPUT = Path(__file__).parent.parent / "experiments-logs" / "roi_suite.samplewise.json"
OUT_JSON = Path(__file__).parent.parent / "experiments-logs" / "roi_suite_extracted.json"
OUT_CSV = Path(__file__).parent.parent / "experiments-logs" / "roi_suite_extracted.csv"


def main():
    with open(INPUT) as f:
        data = json.load(f)

    records = data["records"]
    extracted = []
    for r in records:
        gold = r.get("gold_answer", {})
        rows = gold.get("rows", [])
        cols = gold.get("columns", [])
        extracted.append({
            "record_id": r.get("record_id"),
            "question": r.get("question"),
            "gold_sql": r.get("gold_sql"),
            "table_dimension": f"{len(rows)} x {len(cols)}",
            "gold_answer_headers": cols,
        })

    # Save JSON
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON: {OUT_JSON} ({len(extracted)} records)")

    # Save CSV
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["record_id", "question", "gold_sql", "table_dimension", "gold_answer_headers"])
        for row in extracted:
            writer.writerow([
                row["record_id"],
                row["question"],
                row["gold_sql"],
                row["table_dimension"],
                " | ".join(row["gold_answer_headers"]),
            ])
    print(f"Saved CSV: {OUT_CSV} ({len(extracted)} records)")


if __name__ == "__main__":
    main()
