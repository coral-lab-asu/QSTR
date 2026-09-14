import argparse
import importlib.util
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)


BASELINE_SPECS = {
    "cot": {
        "script_path": os.path.join(ROOT, "baseline-scripts", "COT_gemini.py"),
        "result_subdir": "COT",
        "baseline_label": "COT",
        "default_max_tokens": 4000,
    },
    "zscot": {
        "script_path": os.path.join(ROOT, "baseline-scripts", "ZSCoT.py"),
        "result_subdir": "ZS_COT",
        "baseline_label": "ZS_COT",
        "default_max_tokens": 2000,
    },
}


@dataclass
class BaselineAdapter:
    name: str
    module: Any
    result_subdir: str
    baseline_label: str
    default_max_tokens: int


def safe_model_dir(model: str) -> str:
    return (model or "model").replace("/", "__").strip()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(path: str, payload: Dict[str, Any]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_module_from_path(module_path: str, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_adapter(baseline: str) -> BaselineAdapter:
    spec = BASELINE_SPECS[baseline]
    module = load_module_from_path(spec["script_path"], f"batch_{baseline}")
    return BaselineAdapter(
        name=baseline,
        module=module,
        result_subdir=spec["result_subdir"],
        baseline_label=spec["baseline_label"],
        default_max_tokens=spec["default_max_tokens"],
    )


def load_selected_items(
    adapter: BaselineAdapter,
    dataset_path: str,
    only_universal_ids: bool,
    shuffle: bool,
    seed: int,
    n: int,
) -> List[Tuple[int, Dict[str, Any]]]:
    module = adapter.module
    data = module.read_dataset(dataset_path)
    if only_universal_ids:
        allowed_ids = module.load_universal_sample_ids()
        data = [
            item
            for idx, item in enumerate(data)
            if module.get_sample_id(item, idx) in allowed_ids
        ]
    data.sort(key=lambda item: int(item.get("sample_id", 10**18)))
    if shuffle:
        module.random.Random(seed).shuffle(data)
    if n is not None and n >= 0:
        data = data[:n]
    return list(enumerate(data))


def primitive_cell_schema() -> Dict[str, Any]:
    return {
        "anyOf": [
            {"type": "string"},
            {"type": "number"},
            {"type": "integer"},
            {"type": "boolean"},
            {"type": "null"},
        ]
    }


def table_schema(headers: List[str]) -> Dict[str, Any]:
    width = len(headers)
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "columns": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": width,
                "maxItems": width,
            },
            "rows": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": primitive_cell_schema(),
                    "minItems": width,
                    "maxItems": width,
                },
            },
        },
        "required": ["columns", "rows"],
    }


def zscot_response_format(headers: List[str]) -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "zscot_table_answer",
            "strict": True,
            "schema": table_schema(headers),
        },
    }


def cot_response_format(headers: List[str]) -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "cot_table_answer",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "reasoning_steps": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "step": {"type": "integer"},
                                "name": {"type": "string"},
                                "output": {"type": "string"},
                            },
                            "required": ["step", "name", "output"],
                        },
                    },
                    "final_table": table_schema(headers),
                },
                "required": ["reasoning_steps", "final_table"],
            },
        },
    }


def build_prompts_and_metadata(
    adapter: BaselineAdapter,
    idx: int,
    item: Dict[str, Any],
) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
    module = adapter.module
    sample_id = module.get_sample_id(item, idx)
    question = item.get("question", "")
    context = (item.get("context_full_with_overs") or item.get("context") or item.get("context_full") or "")
    answer = item.get("answer") or {}
    headers = answer.get("columns") or []
    expected_rows = item.get("answer_rows")

    if adapter.name == "zscot":
        system_prompt = module.build_system_prompt(question, headers)
        user_prompt = module.build_user_prompt(context)
        response_format = zscot_response_format(headers)
        metadata = {
            "sample_id": sample_id,
            "record_id": item.get("record_id"),
            "question": question,
            "headers": headers,
            "expected_rows": expected_rows,
        }
        return system_prompt, user_prompt, response_format, metadata

    primary_key = module.normalize_primary_key(item.get("primary_key"))
    row_key_columns, row_key_source = module.derive_row_key_columns(primary_key, headers, expected_rows)
    system_prompt = module.build_system_prompt(question, headers, row_key_columns, primary_key)
    user_prompt = module.build_user_prompt(question, headers, row_key_columns, primary_key, context)
    response_format = cot_response_format(headers)
    metadata = {
        "sample_id": sample_id,
        "record_id": item.get("record_id"),
        "question": question,
        "headers": headers,
        "expected_rows": expected_rows,
        "primary_key": primary_key,
        "row_key_columns": row_key_columns,
        "row_key_source": row_key_source,
    }
    return system_prompt, user_prompt, response_format, metadata


def derive_default_batch_dir(model: str, adapter: BaselineAdapter) -> str:
    return os.path.join(ROOT, "baseline-results", safe_model_dir(model), adapter.result_subdir, "batch")


def derive_default_result_paths(model: str, adapter: BaselineAdapter) -> Dict[str, str]:
    base = os.path.join(ROOT, "baseline-results", safe_model_dir(model), adapter.result_subdir)
    return {
        "predictions": os.path.join(base, "predictions.jsonl"),
        "summary": os.path.join(base, "summary.json"),
        "logs": os.path.join(base, "logs"),
    }


def dump_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def to_jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(mode="json")
        except TypeError:
            return obj.model_dump()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return str(obj)


def cmd_build(args: argparse.Namespace) -> None:
    adapter = load_adapter(args.baseline)
    selected = load_selected_items(
        adapter=adapter,
        dataset_path=args.dataset,
        only_universal_ids=args.only_universal_ids,
        shuffle=args.shuffle,
        seed=args.seed,
        n=args.n,
    )
    batch_dir = args.batch_dir or derive_default_batch_dir(args.model, adapter)
    ensure_dir(batch_dir)

    subset = "universal" if args.only_universal_ids else "dataset"
    tag = args.tag or f"{adapter.result_subdir.lower()}_{subset}_a{args.attempt}"
    requests_out = args.requests_out or os.path.join(batch_dir, f"{tag}.input.jsonl")
    manifest_out = args.manifest_out or os.path.join(batch_dir, f"{tag}.manifest.json")

    request_rows: List[Dict[str, Any]] = []
    manifest_items: List[Dict[str, Any]] = []

    for idx, item in selected:
        system_prompt, user_prompt, response_format, meta = build_prompts_and_metadata(adapter, idx, item)
        sample_id = meta["sample_id"]
        custom_id = f"{sample_id}_a{args.attempt}"
        request_rows.append(
            {
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": args.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": args.temperature,
                    "max_tokens": args.max_tokens,
                    "response_format": response_format,
                },
            }
        )
        manifest_items.append(
            {
                "idx": idx,
                "custom_id": custom_id,
                "sample_id": sample_id,
                "record_id": meta.get("record_id"),
                "question": meta.get("question"),
                "headers": meta.get("headers"),
                "expected_rows": meta.get("expected_rows"),
            }
        )

    dump_jsonl(requests_out, request_rows)
    write_json(
        manifest_out,
        {
            "baseline": args.baseline,
            "baseline_label": adapter.baseline_label,
            "baseline_script": BASELINE_SPECS[args.baseline]["script_path"],
            "dataset": args.dataset,
            "only_universal_ids": args.only_universal_ids,
            "shuffle": args.shuffle,
            "seed": args.seed,
            "n": args.n,
            "attempt": args.attempt,
            "model": args.model,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "requests_path": requests_out,
            "request_count": len(request_rows),
            "items": manifest_items,
        },
    )
    print(f"Wrote {len(request_rows)} requests to {requests_out}")
    print(f"Wrote manifest to {manifest_out}")


def build_openai_client(api_key: str) -> Any:
    if OpenAI is None:
        raise RuntimeError("openai package not installed")
    resolved_key = (api_key or "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if not resolved_key:
        raise RuntimeError("Missing OPENAI_API_KEY or --api-key")
    return OpenAI(api_key=resolved_key)


def cmd_submit(args: argparse.Namespace) -> None:
    client = build_openai_client(args.api_key)
    meta_out = args.meta_out or f"{args.input_jsonl}.batch.json"
    with open(args.input_jsonl, "rb") as f:
        batch_file = client.files.create(file=f, purpose="batch")
    create_kwargs: Dict[str, Any] = {
        "input_file_id": batch_file.id,
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h",
    }
    if args.tag:
        create_kwargs["metadata"] = {"tag": args.tag}
    batch = client.batches.create(**create_kwargs)
    payload = {
        "input_jsonl": args.input_jsonl,
        "batch_file": to_jsonable(batch_file),
        "batch": to_jsonable(batch),
    }
    write_json(meta_out, payload)
    print(f"Uploaded input file: {batch_file.id}")
    print(f"Created batch: {batch.id}")
    print(f"Wrote batch metadata to {meta_out}")


def maybe_download_file(client: Any, file_id: Optional[str], out_path: Optional[str]) -> Optional[str]:
    if not file_id or not out_path:
        return None
    ensure_dir(os.path.dirname(out_path))
    content = client.files.content(file_id)
    content.write_to_file(out_path)
    return out_path


def terminal_batch_status(status: str) -> bool:
    return status in {"completed", "failed", "expired", "cancelled"}


def cmd_download(args: argparse.Namespace) -> None:
    client = build_openai_client(args.api_key)
    batch_id = args.batch_id
    if not batch_id and args.meta_path:
        with open(args.meta_path, "r", encoding="utf-8") as f:
            batch_id = (json.load(f).get("batch") or {}).get("id")
    if not batch_id:
        raise RuntimeError("Provide --batch-id or --meta-path")

    while True:
        batch = client.batches.retrieve(batch_id)
        payload = to_jsonable(batch)
        print(f"Batch {batch_id} status: {payload.get('status')}")
        if not args.wait or terminal_batch_status(payload.get("status", "")):
            break
        time.sleep(args.poll_interval_s)

    if args.status_out:
        write_json(args.status_out, {"batch": payload})
        print(f"Wrote batch status to {args.status_out}")

    output_path = maybe_download_file(client, payload.get("output_file_id"), args.output_jsonl)
    error_path = maybe_download_file(client, payload.get("error_file_id"), args.error_jsonl)
    if output_path:
        print(f"Downloaded batch output to {output_path}")
    if error_path:
        print(f"Downloaded batch error file to {error_path}")


def load_jsonl_map(path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    if not path or not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            custom_id = row.get("custom_id")
            if custom_id:
                rows[str(custom_id)] = row
    return rows


def extract_message_content(body: Dict[str, Any]) -> str:
    choices = body.get("choices") or []
    if not choices:
        return ""
    message = (choices[0] or {}).get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item.get("text"))
        return "".join(parts)
    refusal = message.get("refusal")
    if isinstance(refusal, str):
        return refusal
    return ""


def attempt_number_from_custom_id(custom_id: str) -> int:
    if "_a" not in custom_id:
        return 0
    try:
        return int(custom_id.rsplit("_a", 1)[1])
    except ValueError:
        return 0


def validate_response_for_item(
    adapter: BaselineAdapter,
    text: str,
    item: Dict[str, Any],
    idx: int,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]], str]:
    module = adapter.module
    answer = item.get("answer") or {}
    headers = answer.get("columns") or []
    expected_rows = item.get("answer_rows")
    obj = module.extract_json_obj(text)
    if adapter.name == "zscot":
        ok, table, err = module.validate_table(obj, headers, expected_rows)
        return ok, table, None, err
    ok, payload, err = module.validate_cot_response(obj, headers, expected_rows)
    if not ok or payload is None:
        return False, None, None, err
    return True, payload["pred_table"], payload["reasoning_steps"], ""


def log_batch_attempt(
    log_root: Optional[str],
    custom_id: str,
    baseline_label: str,
    sample_id: int,
    record_id: Any,
    attempt: int,
    response_text: str,
    usage: Dict[str, Any],
    error: Optional[str],
    raw_row: Dict[str, Any],
) -> None:
    if not log_root:
        return
    ensure_dir(log_root)
    path = os.path.join(log_root, f"{custom_id}.json")
    payload = {
        "response_text": response_text,
        "usage": usage,
        "error": error,
        "metadata": {
            "baseline": baseline_label,
            "record_id": record_id,
            "sample_id": sample_id,
            "attempt": attempt,
        },
        "raw_batch_row": raw_row,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def cmd_consume(args: argparse.Namespace) -> None:
    adapter = load_adapter(args.baseline)
    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    module = adapter.module
    raw_data = module.read_dataset(args.dataset or manifest["dataset"])
    item_by_sample_id: Dict[int, Dict[str, Any]] = {}
    for raw_idx, item in enumerate(raw_data):
        item_by_sample_id[module.get_sample_id(item, raw_idx)] = item

    output_rows = load_jsonl_map(args.output_jsonl)
    error_rows = load_jsonl_map(args.error_jsonl)

    result_paths = derive_default_result_paths(args.model or manifest["model"], adapter)
    out_path = args.out or result_paths["predictions"]
    summary_out = args.summary_out or result_paths["summary"]
    log_dir = args.log_dir or result_paths["logs"]
    run_id = args.run_id or f"batch_{adapter.result_subdir.lower()}_a{manifest.get('attempt', 0)}"
    run_log_dir = os.path.join(log_dir, run_id) if log_dir else None

    results: List[Dict[str, Any]] = []
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for entry in manifest.get("items", []):
        idx = int(entry["idx"])
        sample_id = int(entry["sample_id"])
        custom_id = str(entry["custom_id"])
        item = item_by_sample_id.get(sample_id)
        if item is None:
            raise RuntimeError(f"Sample {sample_id} from manifest was not found in dataset")

        record_id = item.get("record_id")
        question = item.get("question", "")
        answer = item.get("answer") or {}
        headers = answer.get("columns") or []
        expected_rows = item.get("answer_rows")

        batch_row = output_rows.get(custom_id) or error_rows.get(custom_id)
        response_text = ""
        error_msg = ""
        usage = {"input_tokens": None, "output_tokens": None, "total_tokens": None}
        success = False
        pred_table = None
        reasoning_steps = None

        if batch_row is None:
            error_msg = "No batch output entry found for custom_id."
        elif batch_row.get("error"):
            error_payload = batch_row.get("error") or {}
            error_msg = f"{error_payload.get('code')}: {error_payload.get('message')}"
        else:
            response = batch_row.get("response") or {}
            body = response.get("body") or {}
            response_text = extract_message_content(body)
            usage_payload = body.get("usage") or {}
            usage = {
                "input_tokens": usage_payload.get("prompt_tokens"),
                "output_tokens": usage_payload.get("completion_tokens"),
                "total_tokens": usage_payload.get("total_tokens"),
            }
            for key in total_usage:
                value = usage.get(key)
                if isinstance(value, (int, float)):
                    total_usage[key] += int(value)
            try:
                ok, table, cot_steps, validation_error = validate_response_for_item(adapter, response_text, item, idx)
                if ok:
                    success = True
                    pred_table = table
                    reasoning_steps = cot_steps
                else:
                    error_msg = validation_error
            except Exception as exc:
                error_msg = str(exc)

        attempt = attempt_number_from_custom_id(custom_id)
        log_batch_attempt(
            log_root=run_log_dir,
            custom_id=custom_id,
            baseline_label=adapter.baseline_label,
            sample_id=sample_id,
            record_id=record_id,
            attempt=attempt,
            response_text=response_text,
            usage=usage,
            error=error_msg or None,
            raw_row=batch_row or {"custom_id": custom_id, "error": {"message": error_msg}},
        )

        result = {
            "record_id": record_id,
            "sample_id": sample_id,
            "original_record_id": record_id,
            "question": question,
            "headers": headers,
            "expected_rows": expected_rows,
            "pred_table": pred_table,
            "success": success,
            "error": None if success else error_msg,
            "attempts": [
                {
                    "attempt": attempt,
                    "response_text": response_text,
                    "usage": usage,
                    "error": None if success else error_msg,
                    "valid": success,
                }
            ],
            "_idx": idx,
        }
        if adapter.name == "cot":
            primary_key = module.normalize_primary_key(item.get("primary_key"))
            row_key_columns, row_key_source = module.derive_row_key_columns(primary_key, headers, expected_rows)
            result["row_key_columns"] = row_key_columns
            result["row_key_source"] = row_key_source
            result["reasoning_steps"] = reasoning_steps
        results.append(result)

    results.sort(key=lambda row: row.get("_idx", 0))
    for row in results:
        row.pop("_idx", None)

    ensure_dir(os.path.dirname(out_path))
    ensure_dir(os.path.dirname(summary_out))
    with open(out_path, "w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    success_results = [row for row in results if row["success"]]
    success_usage_totals = [adapter.module.sum_usage_from_attempts(row.get("attempts", [])) for row in success_results]
    success_n = len(success_results)
    if success_n:
        avg_success_usage = {
            "input_tokens": sum(x["input_tokens"] for x in success_usage_totals) / success_n,
            "output_tokens": sum(x["output_tokens"] for x in success_usage_totals) / success_n,
            "total_tokens": sum(x["total_tokens"] for x in success_usage_totals) / success_n,
        }
    else:
        avg_success_usage = {"input_tokens": None, "output_tokens": None, "total_tokens": None}

    exhausted_failures = [row for row in results if not row["success"]]
    json_failures = [row for row in exhausted_failures if adapter.module.is_json_failure_error(row.get("error"))]
    summary = {
        "n": len(results),
        "success_n": success_n,
        "failure_n": sum(1 for row in results if not row["success"]),
        "usage_total": total_usage,
        "usage_avg_per_successful_sample": avg_success_usage,
        "max_attempts_any_sample": max((len(row.get("attempts", [])) for row in results), default=0),
        "max_retries_used_any_sample": max((len(row.get("attempts", [])) - 1 for row in results), default=0),
        "max_retries_used_failed_sample": max((len(row.get("attempts", [])) - 1 for row in exhausted_failures), default=0),
        "max_retries_used_json_failure": max((len(row.get("attempts", [])) - 1 for row in json_failures), default=0),
        "json_failure_n": len(json_failures),
        "dataset": args.dataset or manifest["dataset"],
        "provider": "openai_batch",
        "model": args.model or manifest["model"],
        "temperature": manifest.get("temperature"),
        "max_tokens": manifest.get("max_tokens"),
        "max_retries": 0,
        "output_path": out_path,
        "log_dir": log_dir,
        "batch_output_jsonl": args.output_jsonl,
        "batch_error_jsonl": args.error_jsonl,
        "manifest": args.manifest,
    }
    with open(summary_out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Wrote predictions to {out_path}")
    print(f"Wrote summary to {summary_out}")
    if run_log_dir:
        print(f"Wrote attempt logs to {run_log_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenAI Batch helpers for COT_gemini.py and ZSCoT.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser_cmd = subparsers.add_parser("build", help="Build OpenAI Batch input JSONL from a baseline")
    build_parser_cmd.add_argument("--baseline", choices=sorted(BASELINE_SPECS), required=True)
    build_parser_cmd.add_argument("--dataset", default=os.path.join(ROOT, "artifacts", "runs", "benchmark", "dataset.jsonl"))
    build_parser_cmd.add_argument("--n", type=int, default=-1)
    build_parser_cmd.add_argument("--only-universal-ids", action="store_true", default=False)
    build_parser_cmd.add_argument("--seed", type=int, default=0)
    build_parser_cmd.add_argument("--shuffle", action="store_true", default=False)
    build_parser_cmd.add_argument("--attempt", type=int, default=0)
    build_parser_cmd.add_argument("--model", default="gpt-4.1")
    build_parser_cmd.add_argument("--temperature", type=float, default=0.0)
    build_parser_cmd.add_argument("--max-tokens", type=int, default=None)
    build_parser_cmd.add_argument("--batch-dir", default=None)
    build_parser_cmd.add_argument("--tag", default=None)
    build_parser_cmd.add_argument("--requests-out", default=None)
    build_parser_cmd.add_argument("--manifest-out", default=None)

    submit_parser = subparsers.add_parser("submit", help="Upload and create an OpenAI Batch job")
    submit_parser.add_argument("--input-jsonl", required=True)
    submit_parser.add_argument("--api-key", default="")
    submit_parser.add_argument("--tag", default=None)
    submit_parser.add_argument("--meta-out", default=None)

    download_parser = subparsers.add_parser("download", help="Check a batch and optionally download outputs")
    download_parser.add_argument("--batch-id", default=None)
    download_parser.add_argument("--meta-path", default=None)
    download_parser.add_argument("--api-key", default="")
    download_parser.add_argument("--wait", action="store_true", default=False)
    download_parser.add_argument("--poll-interval-s", type=int, default=30)
    download_parser.add_argument("--status-out", default=None)
    download_parser.add_argument("--output-jsonl", default=None)
    download_parser.add_argument("--error-jsonl", default=None)

    consume_parser = subparsers.add_parser("consume", help="Convert Batch outputs into baseline result files")
    consume_parser.add_argument("--baseline", choices=sorted(BASELINE_SPECS), required=True)
    consume_parser.add_argument("--manifest", required=True)
    consume_parser.add_argument("--dataset", default=None)
    consume_parser.add_argument("--model", default=None)
    consume_parser.add_argument("--output-jsonl", required=True)
    consume_parser.add_argument("--error-jsonl", default=None)
    consume_parser.add_argument("--out", default=None)
    consume_parser.add_argument("--summary-out", default=None)
    consume_parser.add_argument("--log-dir", default=None)
    consume_parser.add_argument("--run-id", default=None)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "build":
        adapter = load_adapter(args.baseline)
        if args.max_tokens is None:
            args.max_tokens = adapter.default_max_tokens
        cmd_build(args)
        return
    if args.command == "submit":
        cmd_submit(args)
        return
    if args.command == "download":
        cmd_download(args)
        return
    if args.command == "consume":
        cmd_consume(args)
        return
    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
