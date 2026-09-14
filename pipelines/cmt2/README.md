# CMT2 data-generation pipeline

CMT2 is the retained data-generation pipeline for cricket and soccer question
sets. Its canonical flow is:

```text
templates + CSV tables -> generation -> SQL/answer validation -> valid-only deduplication
```

Run commands from the QSTR repository root. Paths are accepted explicitly, so
the commands also work from another directory after QSTR is installed.

The paper-facing cricket inputs are versioned at `data/Cricket_tables/`; the
121 raw seeds are at
`data/data_manual_template/template_q_param_cricket_pk.py`; and the 4,256
generated-query snapshot is at `data/data_final/test_generated_sql_nl.json`.
See `docs/cricket-reproduction.md` for lineage and full reproduction commands.

## Verify the installation

The included fixture needs no API key:

```bash
python -m pipelines.cmt2.pipeline.run run \
  --templates pipelines/cmt2/examples/smoke_templates.py \
  --matches-glob 'pipelines/cmt2/examples/smoke_match.csv' \
  --out-dir artifacts/runs/cmt2-smoke \
  --max-matches 1 \
  --total-examples 3 \
  --seed 42
```

The combined command writes:

- `dataset.no_overs.jsonl`: all successfully generated records;
- `validation.no_overs.json`: execution and answer comparison details;
- `dataset.no_overs.invalid.json`: invalid records with validation details;
- `dataset.no_overs.deduped.jsonl`: valid, unique final records;
- `dataset.no_overs.removed.json`: duplicate-removal audit records;
- `run_manifest.json`: commit, environment, configuration, and output paths.

The command returns a non-zero status if validation finds invalid records. Use
`--allow-invalid` only when reports should be retained without failing an
automation job.

## Production template generation

Use the versioned cricket tables or pass another explicit glob:

```bash
python -m pipelines.cmt2.pipeline.run run \
  --templates pipelines/cmt2/template_q_param_cricket_pk.py \
  --matches-glob 'data/Cricket_tables/*.csv' \
  --out-dir artifacts/runs/cmt2-cricket \
  --max-matches 10 \
  --total-examples 5000 \
  --seed 42
```

Record IDs are derived from the seed, source, template, sample index, question,
and SQL, so equivalent reruns over the same paths are stable.

## Separate stages

Generate only:

```bash
python -m pipelines.cmt2.pipeline.run generate \
  --templates pipelines/cmt2/template_q_param_cricket_pk.py \
  --matches-glob 'data/Cricket_tables/*.csv' \
  --out-dir artifacts/runs/cmt2-cricket \
  --seed 42
```

Validate an existing JSON or JSONL dataset:

```bash
python -m pipelines.cmt2.pipeline.run validate \
  --input artifacts/runs/cmt2-cricket/dataset.no_overs.jsonl \
  --report artifacts/runs/cmt2-cricket/validation.manual.json
```

Deduplicate an existing dataset:

```bash
python -m pipelines.cmt2.pipeline.run deduplicate \
  --input artifacts/runs/cmt2-cricket/dataset.no_overs.jsonl \
  --output artifacts/runs/cmt2-cricket/dataset.manual.deduped.jsonl \
  --removed-output artifacts/runs/cmt2-cricket/dataset.manual.removed.json
```

Validation accepts one read-only `SELECT`/`WITH` statement per record and
rejects mutation, extension loading, and external-file scan SQL.

## CrewAI SQL/NL generation

Install the LLM profile and set the key in the environment or QSTR `.env`:

```bash
python -m pip install -e '.[llm]'
export GEMINI_API_KEY='...'
mkdir -p artifacts/runs/cmt2-crewai
python pipelines/cmt2/run_sql_generation_dedup.py \
  --csv 'data/Cricket_tables/Ball by Ball Commentary & Live Score - AFG vs AUS, 10th Match, Group B.csv' \
  --output artifacts/runs/cmt2-crewai/sql.json \
  --progress artifacts/runs/cmt2-crewai/sql.progress.json \
  --target 5000 \
  --diversity-csv data/data_manual_template/cricket_sql_question_templates_1000.csv
```

The files directly under `pipelines/cmt2/` remain compatibility entry points.
New automation should use `pipelines.cmt2.pipeline.run` and import reusable
functions from `pipelines.cmt2.pipeline.dataset_pipeline`.

## Tests

```bash
python -m pytest pipelines/cmt2/tests -q
```

The integration test runs the same credential-free fixture and is skipped only
when `pandas` or `duckdb` is not installed.
