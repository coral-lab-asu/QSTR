# CMT2 smoke fixture

These tiny, synthetic files exercise generation, SQL execution validation,
and result-based deduplication without model credentials or external data.
They are test fixtures only and are not representative training data.

From the QSTR repository root:

```bash
python -m pipelines.cmt2.pipeline.run run \
  --templates pipelines/cmt2/examples/smoke_templates.py \
  --matches-glob 'pipelines/cmt2/examples/smoke_match.csv' \
  --out-dir artifacts/runs/cmt2-smoke \
  --max-matches 1 \
  --total-examples 3 \
  --seed 42
```

The expected result is three valid generated records and two retained records;
the two total-run templates intentionally produce the same result so one is
removed by deduplication.
