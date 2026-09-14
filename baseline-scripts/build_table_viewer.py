import argparse
import json
import os
from typing import Any, Dict, List


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def read_dataset(path: str) -> List[Dict[str, Any]]:
    if path.endswith(".jsonl"):
        return read_jsonl(path)
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict) and "records" in obj:
        return obj["records"]
    if isinstance(obj, list):
        return obj
    raise ValueError(f"Unsupported dataset format: {path}")


def sample_id_of(item: Dict[str, Any]) -> Any:
    if "sample_id" in item:
        return item.get("sample_id")
    if "record_id" in item:
        return item.get("record_id")
    return None


def main():
    ap = argparse.ArgumentParser(description="Embed dataset + predictions into the viewer HTML")
    ap.add_argument("--dataset", required=True, help="Path to dataset (json/jsonl)")
    ap.add_argument("--predictions", required=True, help="Path to predictions jsonl")
    ap.add_argument("--eval", default="", help="Optional eval samplewise jsonl")
    ap.add_argument("--template", default="baseline-results/zscot_viewer.html")
    ap.add_argument("--out", default="baseline-results/zscot_viewer.html")
    ap.add_argument("--limit", type=int, default=100, help="Limit number of samples to embed (default: 100)")
    args = ap.parse_args()

    dataset = read_dataset(args.dataset)
    preds = read_jsonl(args.predictions)
    evals = read_jsonl(args.eval) if args.eval else []

    if args.limit and args.limit > 0:
        preds = preds[: args.limit]
        evals = evals[: args.limit]

        keep_ids = set()
        for row in preds:
            sid = sample_id_of(row)
            if sid is not None:
                keep_ids.add(sid)
        for row in evals:
            sid = sample_id_of(row)
            if sid is not None:
                keep_ids.add(sid)

        dataset = [row for row in dataset if sample_id_of(row) in keep_ids]

    with open(args.template, "r", encoding="utf-8") as f:
        html = f.read()

    data_obj = {
        "dataset": dataset,
        "preds": preds,
        "evals": evals,
    }
    replacement = f"window.__VIEWER_DATA__ = {json.dumps(data_obj, ensure_ascii=False)};"
    placeholder = """window.__VIEWER_DATA__ = {\n        dataset: [],\n        evals: [],\n        preds: []\n      };"""
    if placeholder in html:
        out_html = html.replace(placeholder, replacement, 1)
    else:
        start_marker = "window.__VIEWER_DATA__ = "
        end_marker = ";\n    </script>"
        if start_marker not in html:
            raise RuntimeError("Could not find the viewer data block.")
        prefix, rest = html.split(start_marker, 1)
        if end_marker not in rest:
            raise RuntimeError("Malformed embedded viewer data block.")
        _, suffix = rest.split(end_marker, 1)
        out_html = prefix + replacement + end_marker + suffix

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(out_html)

    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
