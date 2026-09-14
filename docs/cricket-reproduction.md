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

The original CMT2 workspace retains duplicate-result and zero/NaN reports,
but those intermediate reports are not included in this QSTR release.
The 4,256 records match the item-ID sequence of CMT2's historical
`test_generated_sql_nl_progress_5k_4_removed.json`; subsequent QSG edits changed
SQL and some question text. This is not the 3,781-record CMT2 retained subset,
and its historical selection should not be described as current validation.
The checked-in files preserve the QSG snapshot; the current CMT2 flow provides
validation and deduplication for new runs.

The hosted command above writes generation/progress files, not the combined
CMT2 run manifest. Preserve its configuration separately. To validate those
new SQL candidates, supply the source CSV explicitly (the historical JSON
container stores it outside individual records):

```bash
python -m pipelines.cmt2.pipeline.run validate \
  --input artifacts/runs/cricket-query-bank/generated.json \
  --csv 'data/Cricket_tables/Ball by Ball Commentary & Live Score - AFG vs AUS, 10th Match, Group B.csv' \
  --report artifacts/runs/cricket-query-bank/validation.json
```

Without stored answers this checks SQL execution only. Review the report and
pass the generated query bank through the combined command in step 4 to
materialize answers and obtain valid-only deduplicated records.

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

### Recheck the historical answers

```bash
python -m pipelines.cmt2.pipeline.run validate \
  --input data/data_final/test_generated_sql_nl.ground_truth.json \
  --report artifacts/runs/cricket-audit/validation.json
```

This command returns status 1 when any record fails. Use `--allow-invalid`
only to collect diagnostics without a failing exit status. The validator
compares `ground_truth_table` with SQL execution, preserving row multiplicity
while ignoring row order. It does not establish that the SQL answers the
natural-language question correctly. See the [verification record](verification.md)
for the observed results and limits of testing.

- Cite the exact QSTR commit and archive it with a persistent DOI/tag.
- Report 638 tables, 150,666 table rows, 121 hand-authored seeds, and 4,256
  generated queries.
- Report that 4,239 ground-truth records are resolved and 17 are unresolved.
- Report current execution/answer validation separately from those structural
  counts; do not equate a stored answer with a verified answer.
- Preserve `data/MANIFEST.sha256` with the archived release.
- Supply the missing cricket-table source URL, retrieval date, attribution,
  and license before making the artifact public.
- For new hosted runs, preserve prompts, model/version, parameters, failures,
  validation reports, deduplication reports, and the generated run manifest.
