# Architecture and execution flow

## Canonical flow

```text
templates + match tables
        |
        v
parameter initialization and SQL materialization
        |
        v
DuckDB execution -> answer/context/provenance record
        |
        v
model inference -> predictions and raw responses
        |
        v
normalization -> exact/PK/numeric metrics -> analysis artifacts
```

## QSG components

- `src/core/generate_questions.py` builds coverage-oriented datasets.
- `src/core/generate_questions_split.py` adds provenance, difficulty, and
  split-aware generation.
- `src/core/sql_param_initializer.py` samples entity and temporal parameters.
- `src/core/sql_crew_agents_v2.py` contains the current reusable CrewAI SQL/NL
  generation implementation; the dedup runner adds resumable hard dedupe.
- `src/inference/service.py` is the shared model-inference abstraction used by
  baseline runners.
- `src/eval/` contains SQL/table/PK/numeric evaluation and duplicate tooling.
- `baseline-scripts/` contains research-specific prompting strategies. These
  should become thin strategy adapters over shared inference and serialization
  utilities.

## CMT2 components

CMT2 preserves the older but still useful data-generation path under
`pipelines/cmt2/`:

1. `pipelines/cmt2/generate_questions.py` generates answer-grounded JSON/JSONL records.
2. `pipelines/cmt2/sql_crew_agents.py` or `sql_crew_agents_v2.py` generates SQL and NL data
   through CrewAI.
3. `pipelines/cmt2/pipeline/dataset_pipeline.py` executes SQL against the source table and
   compares stored answers.
4. The same module computes source/result fingerprints for deterministic
   deduplication.
5. `pipelines/cmt2/pipeline/run.py` exposes the stages through one command-line interface.

The legacy scripts remain available for compatibility while the pipeline
module becomes the documented integration point.
