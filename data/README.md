# Cricket data release

This directory contains the versioned cricket inputs and generated query
artifacts used by QSTR. It is intentionally self-contained so a paper
reviewer can inspect the historical dataset and run new generation without
obtaining the original authors' workstation.

## Contents

| Path | Role | Count |
| --- | --- | ---: |
| `Cricket_tables/*.csv` | Ball-by-ball source tables | 638 tables / 150,666 rows |
| `data_manual_template/template_q_param_cricket_pk.py` | Hand-authored seed queries with primary keys | 121 templates |
| `data_manual_template/cricket_sql_question_templates_1000.csv` | Surviving auxiliary diversity bank; exact historical input unverified | 1,000 prompts |
| `data_final/test_generated_sql_nl.json` | Curated queries generated from the seed layer | 4,256 queries |
| `data_final/test_generated_sql_nl.ground_truth.json` | Generated queries enriched with source-table paths and executed results | 4,256 records |
| `MANIFEST.sha256` | SHA-256 checksum for every released data file | 642 entries |

The 4,256-query file is **generated output**, not the seed bank. The canonical
seed bank contains 121 templates. A byte-identical copy remains at
`pipelines/cmt2/template_q_param_cricket_pk.py`, where the CMT2 generator can
load it directly.

## Table schema

All 638 CSV files use the same 16 columns:

```text
raw_data, overs, runs, team_runs, commentary, bowler, batsman,
batsman_runs, batsman_fours, batsman_sixes, batsman_bowls_faced,
bowler_bowls_done, bowler_runs_given, bowler_wickets, dismissal,
runs_given_bool
```

The historical file paths inside the ground-truth data begin with
`data/Cricket_tables/`. That layout is preserved so the records execute from
the repository root without path rewriting.

## Integrity and known limitations

Run the release verifier after cloning:

```bash
python scripts/verify_cricket_release.py
```

It checks every checksum, table count and schema, seed count, generated-record
count, and source-table reference. Of the 4,256 ground-truth records, 4,239
have a source table and stored execution result. This is a structural count,
not a claim that all 4,239 answers pass current SQL re-execution. The verifier
does not execute SQL. The remaining 17 historical
records have both fields set to null and are retained for a transparent audit
trail; downstream evaluation should exclude them unless they are repaired and
revalidated.

A full re-execution during the documentation audit passed 4,222 records,
with 17 missing sources and 17 stored-answer mismatches. See the
[verification record](../docs/verification.md) for reproduction commands and
affected indices. The historical files remain unchanged.

The generated query IDs are not globally unique: there are 3,709 distinct
`item_id` values among 4,256 records. Consumers should use list position or
derive a stable record hash when a unique key is required.

The historical generation metadata names its diversity input
`cricket_sql_question_templates_1000_with_sql.csv`. That exact file is not
present in the source workspace. The surviving 1,000-row file has the columns
`template_id`, `category`, and `question_template` and is published here as
`cricket_sql_question_templates_1000.csv`. It is suitable for the current
loader, but byte identity with the historical input cannot be established.

## Provenance

- Cricket tables, the 121-template seed file, and the surviving diversity bank
  were imported from the local CMT2 working tree. The same 638 table files were
  independently present in the local QSG worktree and matched byte-for-byte.
- The two `data_final` files were exported from QSG reference
  `origin/naman-exp` at commit
  `11b69bcf66f7f649c030baa2465770ee38163915`.
- The QSTR import did not modify the original QSG or CMT2 working trees.

The source workspace did not contain an authoritative upstream URL, download
date, or data license for the cricket CSVs. Those fields must be supplied by
the paper authors before a public archival release. This repository records
the gap rather than guessing attribution or licensing terms.

See [`docs/cricket-reproduction.md`](../docs/cricket-reproduction.md) for the
complete generation, enrichment, validation, and deduplication workflow.

## Updating the release

After an intentional data change, rebuild and verify checksums:

```bash
python scripts/verify_cricket_release.py --write-manifest
```

Review the resulting data diff and updated counts before committing. New run
outputs belong under `artifacts/runs/`, which remains ignored by Git.
