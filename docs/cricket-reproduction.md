# Cricket query-generation reproduction

This runbook separates immutable paper artifacts from new experiment output.
The checked-in 121 seeds and 4,256 generated queries are historical snapshots;
new runs are written under `artifacts/runs/` and must not overwrite them.

## 1. Install and verify

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python scripts/doctor.py
python scripts/verify_cricket_release.py
python -m pytest -q
```

Install `.[llm]` and configure `GEMINI_API_KEY` only for hosted seed expansion.
Table instantiation, SQL execution, validation, and deduplication do not need a
model credential.

## 2. Expand the 121 seeds with a hosted model

The historical run used one cricket table, 121 base templates, ten rounds per
template, a target of 10,000 unique candidates, and 20 sampled diversity ideas
per round. It recorded 8,037 generated candidates and 1,813 failures before
later curation produced the checked-in 4,256-query snapshot.

Create a new, non-canonical run with:

```bash
mkdir -p artifacts/runs/cricket-query-bank
python pipelines/cmt2/run_sql_generation_dedup.py \
  --csv 'data/Cricket_tables/Ball by Ball Commentary & Live Score - AFG vs AUS, 10th Match, Group B.csv' \
  --output artifacts/runs/cricket-query-bank/generated.json \
  --progress artifacts/runs/cricket-query-bank/progress.json \
  --target 10000 \
  --rounds-per-template 10 \
  --diversity-csv data/data_manual_template/cricket_sql_question_templates_1000.csv \
  --diversity-k 20
```

Hosted-model output is not expected to be byte-for-byte reproducible. Record
the provider, exact model/version, dependency lock, prompt configuration,
temperature if configurable, timestamps, and response IDs in the run manifest.
Never commit an API key or place it in a command argument.

The exact historical post-generation curation inputs were not all retained:
the old deduplication script depended on intermediate duplicate-result and
zero/NaN reports. Therefore the checked-in 4,256-query file is the authoritative
historical artifact, while the current CMT2 validation/deduplication flow is the
reproducible process for new runs.

## 3. Enrich the checked-in queries with cricket tables

This deterministic command executes the 4,256 queries against compatible
tables and writes both enriched records and a manual-review file:

```bash
mkdir -p artifacts/runs/cricket-enrichment
python -m src.core.generate_questions \
  --enrich_existing_dataset data/data_final/test_generated_sql_nl.json \
  --matches_glob 'data/Cricket_tables/*.csv' \
  --enrich_output_path artifacts/runs/cricket-enrichment/ground_truth.json \
  --manual_review_path artifacts/runs/cricket-enrichment/manual_review.json
```

Compare counts and failures with the published snapshot. Do not overwrite the
versioned ground-truth file without reviewing every changed record and
regenerating `data/MANIFEST.sha256`.

## 4. Run generation, validation, and deduplication end to end

The combined CMT2 command instantiates query templates on cricket tables,
executes read-only SQL, separates invalid records, deduplicates valid results,
and writes a run manifest:

```bash
python -m pipelines.cmt2.pipeline.run run \
  --templates data/data_final/test_generated_sql_nl.json \
  --matches-glob 'data/Cricket_tables/*.csv' \
  --out-dir artifacts/runs/cricket-cmt2 \
  --max-matches 10 \
  --total-examples 5000 \
  --samples-per-template-per-match 1 \
  --seed 42
```

Set `--max-matches 0 --total-examples 0` only when an exhaustive run is
intended; the Cartesian expansion can be very large. The output directory
contains generated datasets with and without over markers, validation reports,
invalid records, deduplicated records, removed-duplicate records, and
`run_manifest.json`.

The CMT2 loader also normalizes list fields in older progress files where
`variables` or `paraphrases` were serialized using Python-list notation. The
checked-in curated query bank already stores those fields as JSON arrays.

## 5. Paper artifact checklist

- Cite the exact QSTR commit and archive it with a persistent DOI/tag.
- Report 638 tables, 150,666 table rows, 121 hand-authored seeds, and 4,256
  generated queries.
- Report that 4,239 ground-truth records are resolved and 17 are unresolved.
- Preserve `data/MANIFEST.sha256` with the archived release.
- Supply the missing cricket-table source URL, retrieval date, attribution,
  and license before making the artifact public.
- For new hosted runs, preserve prompts, model/version, parameters, failures,
  validation reports, deduplication reports, and the generated run manifest.
