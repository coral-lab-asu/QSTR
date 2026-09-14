# Data contracts

## Dataset record

The preferred record contains:

- stable `record_id`
- source identifier such as `match_path` or `csv_path`
- `template_id` or `item_id`
- natural-language `question`
- executable `sql` using table name `df`
- `params_raw` and optional `params_sql`
- `answer` with `columns` and `rows`
- optional `context`, `context_full`, and provenance metadata

## Validation report

Validation reports contain one entry per input record and include:

- source CSV
- whether SQL was present
- execution status and error, if any
- result row/column counts
- normalized result signature
- whether the stored answer matches re-execution

Validation executes only one read-only `SELECT` or `WITH` statement against
the registered `df` table. Mutation, extension loading, and external-file scan
operations are rejected. Result rows are compared as a multiset because SQL
row order is undefined without a complete ordering and tied sort keys can be
returned in either order. Column order and duplicate-row multiplicity remain
significant.

## Deduplication

Deduplication is scoped by source table. The preferred fingerprint is the
normalized answer; normalized SQL is the fallback when an answer is absent.
The first record is retained and later records are written to a removal report
with their original index and duplicate predecessor.

The combined CMT2 command deduplicates only records that passed validation.
Invalid records are preserved separately for diagnosis and are never promoted
to the final deduplicated dataset.

## Compatibility

Readers should accept both JSONL records and JSON objects containing `final`,
`records`, or `items`. New writers should prefer JSONL for large datasets and
JSON summaries for aggregate metadata.
