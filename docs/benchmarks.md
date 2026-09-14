# Running benchmarks

Run these commands from the QSTR repository root after installing `.[dev]`.
All benchmark runners default to `artifacts/runs/benchmark/dataset.jsonl`.
Create that file before inference. It contains question, commentary, answer,
source path, unique `record_id`, and numeric `sample_id` fields.

## Prepare the published ground truth

```bash
python -m scripts.prepare_benchmark
```

This reads the published ground-truth snapshot, re-executes SQL, excludes
missing sources and mismatched answers, and writes the accepted JSONL plus
`dataset.manifest.json`. The manifest records input/output checksums and
excluded source indices. Original release files remain unchanged. This is
an execution-validated subset, not certification of question semantics.

Preparation intentionally supplies **full commentary with over markers**.
This must be reported as the benchmark context policy. It differs from the
generator's focused context; full-context preparation is not a reproduction
of historical focused-context paper scores.

## Generate new records, then prepare them

```bash
python -m pipelines.cmt2.pipeline.run run \
  --templates data/data_final/test_generated_sql_nl.json \
  --matches-glob 'data/Cricket_tables/*.csv' \
  --out-dir artifacts/runs/benchmark-generation \
  --max-matches 1 --total-examples 20 --seed 42
python -m scripts.prepare_benchmark \
  --input artifacts/runs/benchmark-generation/dataset.no_overs.deduped.jsonl
```

Freeze the resulting dataset and manifest across model comparisons. Subsequent
preparation overwrites this run output, so choose a different `--output` path
when preserving an earlier benchmark. Record the QSTR commit and dependency
versions alongside the manifest.

## Build prompts without model calls

```bash
python baseline-scripts/openai_batch_baselines.py build \
  --baseline cot --n 2 --batch-dir artifacts/runs/benchmark-prompts
```

The `build` subcommand creates request files locally. It does not submit a
batch or measure model quality. The separate `submit` command incurs provider
usage and requires credentials.

## Run inference and evaluation

Install `.[llm]` and configure the provider credentials in `.env`. For an
OpenAI-compatible server you operate, use its model identifier and endpoint:

```bash
python baseline-scripts/COT.py \
  --dataset artifacts/runs/benchmark/dataset.jsonl \
  --provider openai --model YOUR_MODEL --base-url http://localhost:8002/v1 \
  --n 20 --workers 1 \
  --log-dir artifacts/runs/benchmark-cot/logs --run-id cot \
  --out artifacts/runs/benchmark-cot/predictions.jsonl \
  --summary-out artifacts/runs/benchmark-cot/summary.json
python baseline-scripts/eval_table_predictions.py \
  --dataset artifacts/runs/benchmark/dataset.jsonl \
  --predictions artifacts/runs/benchmark-cot/predictions.jsonl \
  --out-samplewise artifacts/runs/benchmark-cot/eval.jsonl \
  --out-summary artifacts/runs/benchmark-cot/eval.summary.json
```

Replace `YOUR_MODEL` with the exact served model. Other runners expose their
options with `--help`; provider/model defaults differ, so set them explicitly.
The split-analysis runner additionally needs split/provenance metadata for
meaningful subgroup reporting; a standard prepared dataset does not create
those annotations.

## Historical subset selection

Universal-ID filtering defaults to off, including offline batch construction.
For a historical subset, set `QSTR_SAMPLE_IDS` to a JSON file containing
`{"sample_ids": [0, 2, 5]}` and enable `--only-universal-ids`. ReAct_Gemini,
RowCOT_Gemini, and RowCOT_Modular require a boolean value for this option;
other runners use a flag. IDs must refer to the selected prepared dataset;
do not reuse historical indices against a different dataset.

Raw seed/query JSON is not a benchmark input. Shared runner loaders reject
missing question/context/answer fields before provider calls. For explicitly
supplied generated inputs, empty focused context falls back to `context_full`.
