# CMT2 data-generation pipeline

CMT2 is the retained data-generation pipeline for cricket and soccer question
sets. It includes template generation, CrewAI SQL/NL generation, SQL execution
validation, answer validation, and deduplication.

## Pipeline stages

1. Generate records from templates:

   ```bash
   python pipeline/run.py generate \
     --templates template_q_param_cricket_pk.py \
     --matches-glob 'Cricket_tables/*.csv' \
     --out-dir output/dataset_runs/cmt2 \
     --max-matches 10 \
     --total-examples 5000 \
     --seed 42
   ```

2. Validate generated SQL and stored answers:

   ```bash
   python pipeline/run.py validate \
     --input output/dataset_runs/cmt2/dataset.no_overs.jsonl \
     --report output/dataset_runs/cmt2/validation.no_overs.json
   ```

3. Deduplicate records by source and normalized result (or SQL fallback):

   ```bash
   python pipeline/run.py deduplicate \
     --input output/dataset_runs/cmt2/dataset.no_overs.jsonl \
     --output output/dataset_runs/cmt2/dataset.no_overs.deduped.jsonl \
     --removed-output output/dataset_runs/cmt2/dataset.no_overs.removed.json
   ```

The combined `run` command performs all three stages and writes a validation
report, deduplicated dataset, and removal report beside the generated dataset.

## CrewAI SQL/NL generation

The existing resumable generator remains available:

```bash
export GEMINI_API_KEY='...'
python run_sql_generation_dedup.py \
  --csv 'Cricket_tables/<match>.csv' \
  --output output/cmt2_sql.json \
  --progress output/cmt2_sql.progress.json \
  --target 5000
```

Validate and deduplicate its output through `pipeline/run.py` using the same
commands above. The source modules remain available for compatibility; new
automation should call the pipeline CLI or import `pipeline.dataset_pipeline`.

## Data and artifacts

`Cricket_tables/` and `Soccer_tables/` are source data. Existing `output/`,
evaluation logs, and run directories are generated artifacts and are not part
of the canonical code path. The local `.gitignore` excludes transient output
and credentials while preserving the source code and templates.

## Development check

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
