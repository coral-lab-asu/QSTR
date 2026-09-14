import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from src.cli.run_settings_gemini import (
    SCHEMA_COLS,
    USER_SCHEMA_Q_TO_SQL,
    SYSTEM_PROMPT_SQL,
    _get_default_api_key,
    _get_default_base_url,
    _load_dataset_any,
    build_llm_client,
    call_llm_sql,
    df_to_answer_json,
    ensure_dir,
    execute_sql_on_match_csv,
    get_schema_sample_rows,
)


def write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _print_progress(done: int, total: int) -> None:
    pct = (done / total * 100.0) if total else 100.0
    print(f"\rProgress: {done}/{total} ({pct:.1f}%)", end="", flush=True)


def _finalize_progress() -> None:
    print("", flush=True)


def _expected_headers(item: Dict[str, Any]) -> List[str]:
    table = item.get("ground_truth_table") or {}
    cols = table.get("columns") or []
    return [str(c) for c in cols]


def _gold_sql(item: Dict[str, Any]) -> str:
    sql = item.get("original_sql")
    if isinstance(sql, str) and sql.strip():
        return sql
    sql = item.get("sql")
    return sql if isinstance(sql, str) else ""


def _executed_sql(item: Dict[str, Any]) -> str:
    sql = item.get("sql")
    return sql if isinstance(sql, str) else ""


def run_schema_q_to_sql_ground_truth(
    dataset_path: str,
    out_path: str,
    *,
    provider: str,
    api_key: str,
    model_name: str,
    workers: int,
    base_url: Optional[str] = None,
    max_rows: int = 200,
    n_samples: int = 0,
) -> Dict[str, Any]:
    ensure_dir(os.path.dirname(out_path) or ".")

    data = _load_dataset_any(dataset_path)
    if not data:
        raise RuntimeError(f"Empty dataset: {dataset_path}")

    items = data[:n_samples] if n_samples and n_samples > 0 else data
    total = len(items)
    client = build_llm_client(provider=provider, model_name=model_name, api_key=api_key, base_url=base_url)

    outputs: List[Optional[Dict[str, Any]]] = [None] * total

    def run_one(idx: int, item: Dict[str, Any]) -> Dict[str, Any]:
        rec = dict(item)
        rec["setting"] = "SCHEMA_Q_TO_SQL"
        rec["pred_sql"] = None
        rec["pred_result"] = None
        rec["exec_ok"] = False
        rec["exec_error"] = None
        rec["usage"] = {}
        rec["raw_model_output"] = None
        rec["gold_sql"] = _gold_sql(rec)
        rec["executed_ground_truth_sql"] = _executed_sql(rec)

        question = rec.get("question") or ""
        match_path = rec.get("match_path")
        expected_headers = _expected_headers(rec)
        schema_rows = get_schema_sample_rows(match_path, n=3)

        rec["schema_cols"] = SCHEMA_COLS
        rec["expected_headers"] = expected_headers

        if not match_path or not os.path.exists(match_path):
            rec["exec_error"] = f"match_path missing or not found: {match_path}"
            return {"idx": idx, "record": rec}

        if not question:
            rec["exec_error"] = "missing question"
            return {"idx": idx, "record": rec}

        if not expected_headers:
            rec["exec_error"] = "missing ground_truth_table columns"
            return {"idx": idx, "record": rec}

        try:
            user_prompt = USER_SCHEMA_Q_TO_SQL.format(
                schema_json=json.dumps(SCHEMA_COLS, ensure_ascii=False),
                schema_rows_json=json.dumps(schema_rows, ensure_ascii=False),
                headers_json=json.dumps(expected_headers, ensure_ascii=False),
                question=question,
            )
            model_out = call_llm_sql(client, provider, model_name, user_prompt)
            pred_sql = model_out["sql"].strip()

            rec["pred_sql"] = pred_sql
            rec["usage"] = model_out.get("_usage") or {}
            rec["raw_model_output"] = model_out
            rec["system_prompt"] = SYSTEM_PROMPT_SQL
            rec["user_prompt"] = user_prompt

            out_df = execute_sql_on_match_csv(match_path, pred_sql)
            rec["pred_result"] = df_to_answer_json(out_df, max_rows=max_rows)
            rec["exec_ok"] = True
        except Exception as e:
            rec["exec_error"] = str(e)

        return {"idx": idx, "record": rec}

    done = 0
    _print_progress(done, total)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run_one, idx, item) for idx, item in enumerate(items)]
        for fut in as_completed(futs):
            res = fut.result()
            outputs[res["idx"]] = res["record"]
            done += 1
            if done % 5 == 0 or done == total:
                _print_progress(done, total)
    _finalize_progress()

    final_rows = [r for r in outputs if r is not None]
    write_json(out_path, final_rows)

    exec_ok = sum(1 for r in final_rows if r.get("exec_ok"))
    exec_fail = len(final_rows) - exec_ok
    summary = {
        "dataset_path": dataset_path,
        "out_path": out_path,
        "provider": provider,
        "model": model_name,
        "num_records": len(final_rows),
        "exec_ok": exec_ok,
        "exec_fail": exec_fail,
    }
    summary_path = os.path.splitext(out_path)[0] + ".summary.json"
    write_json(summary_path, summary)
    return summary


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dataset_path",
        default="data/data_final/test_generated_sql_nl.ground_truth.json",
        help="Path to the enriched ground-truth JSON dataset.",
    )
    ap.add_argument(
        "--out_path",
        default="data/data_final/test_generated_sql_nl.schema_q_to_sql_predictions.json",
        help="Path to the output JSON with predictions attached.",
    )
    ap.add_argument(
        "--provider",
        default="google",
        choices=["google", "openai", "deepinfra"],
        help="LLM provider backend.",
    )
    ap.add_argument(
        "--base_url",
        default="",
        help="Optional base URL for OpenAI-compatible providers.",
    )
    ap.add_argument(
        "--api_key",
        default="",
        help="API key. If omitted, uses provider-specific env var.",
    )
    ap.add_argument("--model", default="gemini-2.5-flash")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max_rows", type=int, default=200)
    ap.add_argument(
        "--n",
        type=int,
        default=0,
        help="If >0, run only the first N records.",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    provider = (args.provider or "google").lower().strip()
    api_key = args.api_key or _get_default_api_key(provider)
    if not api_key:
        raise RuntimeError(
            "Provide an API key via --api_key or provider env var: GEMINI_API_KEY / OPENAI_API_KEY / DEEPINFRA_API_KEY"
        )

    base_url = (args.base_url or "").strip() or _get_default_base_url(provider)

    started = time.time()
    summary = run_schema_q_to_sql_ground_truth(
        dataset_path=args.dataset_path,
        out_path=args.out_path,
        provider=provider,
        api_key=api_key,
        model_name=args.model,
        workers=args.workers,
        base_url=base_url,
        max_rows=args.max_rows,
        n_samples=args.n,
    )
    summary["elapsed_seconds"] = round(time.time() - started, 2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()


# python -m src.cli.run_schema_q_to_sql_ground_truth \
#   --dataset_path data/data_final/test_generated_sql_nl.ground_truth.json \
#   --out_path data/data_final/test_generated_sql_nl.schema_q_to_sql_predictions.json \
#   --provider google \
#   --n 10 \
#   --model gemini-2.5-flash \
#   --workers 8
