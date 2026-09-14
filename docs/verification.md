# Verification record

This audit covers the cricket data introduced in commit
`ac9e1746e6401e6501f082d5e512dc22d1d73544` and the accompanying documentation.
Data files are preserved byte-for-byte; pipeline fixes and documentation are
recorded in the commit containing this report.

## Release integrity

`python scripts/verify_cricket_release.py` verifies 642 SHA-256 entries,
638 tables with 150,666 rows, 121 base seed templates, 1,000 auxiliary prompts,
and 4,256 generated records. The enriched snapshot has 4,239 source/result
mappings and 17 null mappings. Integrity verification does not execute SQL.

## Full historical answer check

From the repository root, with the core dependencies installed:

```bash
python -m pipelines.cmt2.pipeline.run validate \
  --input data/data_final/test_generated_sql_nl.ground_truth.json \
  --report artifacts/runs/cricket-audit/validation.json
```

Observed with Python 3.12 and DuckDB 1.5.5: 4,222 passed, 17 missing sources,
17 stored-answer mismatches. Exit status 1 is expected for these findings.
The audit uses the published SQL and source paths and compares stored
`ground_truth_table` contents as row multisets, with numeric normalization
to 12 decimal places. SQL without complete ordering, tied LIMIT results,
window-function ties, or numerical differences may affect reruns; a mismatch
requires investigation before assigning a cause.

Zero-based array indices with answer mismatches in this run:

```text
39, 958, 1047, 1098, 1204, 1269, 1294, 1317, 1513, 2012,
2066, 2118, 3124, 3316, 3340, 4243, 4246
```

Use array indices because historical `item_id` values are not unique. The
source snapshot has not been silently repaired or filtered. Evaluation should
record its actual accepted subset and report rejected records separately.

## End-to-end sample check

```bash
python -m pipelines.cmt2.pipeline.run run \
  --templates data/data_final/test_generated_sql_nl.json \
  --matches-glob 'data/Cricket_tables/*.csv' \
  --out-dir artifacts/runs/cricket-documentation-smoke \
  --max-matches 1 --total-examples 20 --seed 42
```

The release smoke check generated 20 records, validated all 20, and retained
20 after deduplication. The tiny synthetic fixture separately exercises an
intentional duplicate (3 valid, 2 retained). The combined CLI validates and
deduplicates the `no_overs` dataset; the `with_overs` file shares its SQL and
answers but is not separately validated by that command.

Unit/integration tests run with `python -m pytest -q`. Core versions are
listed in `requirements-core.lock`; that file pins direct dependencies and
is not a complete transitive environment lock.

## Scope and remaining gaps

No hosted-model expansion or model inference was run in this audit. The
documented 5,000-example command is a recipe, not a reported completed run.
SQL checks do not verify question semantics, paper metrics, or exact
supporting-row attribution. The current CrewAI implementation defaults to
`gemini/gemini-2.5-flash-lite` and samples temperature between 0.6 and 1.1;
this does not establish the model used for the historical data.

The exact historical diversity file named `*_with_sql.csv`, upstream table
source/retrieval metadata, and data license remain unverified. See the
[data card](../data/README.md) and [reproduction guide](cricket-reproduction.md).
