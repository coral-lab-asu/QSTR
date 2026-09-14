# QSTR repository map

QSTR is a fresh-history consolidation of three sources:

1. QSG `naman-exp`: reusable generation, inference, evaluation, baseline, and
   analysis code.
2. QSG `naman_syn_data`: synthetic-data scripts and compact experiment assets.
3. CMT2: the standalone generation pipeline committed as `f0ebf4d`.

The new repository intentionally does not preserve the old Git object graph.
The original SHAs and branch roles remain documented for reproducibility.

## Migration rules

- Prefer `src/` for reusable QSG functionality.
- Prefer `pipelines/cmt2/pipeline/` for CMT2 record loading, validation, and
  deduplication.
- Treat files directly under `pipelines/cmt2/` as compatibility entry points
  until their logic is migrated behind the shared pipeline API.
- Keep synthetic-data experiments isolated under
  `pipelines/synthetic_data/synData/` until their data contracts are aligned
  with the main dataset schema.
