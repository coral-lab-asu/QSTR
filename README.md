# QSTR

QSTR is the consolidated, sanitized knowledge-transfer repository for the
Question and SQL Generation work. It combines the reusable QSG code, the CMT2
data-generation pipeline, and the synthetic-data experiments from
`naman_syn_data`.

## Repository layout

| Area | Location | Purpose |
| --- | --- | --- |
| QSG core | `src/` | Dataset generation, inference, SQL agents, and evaluation |
| Baseline experiments | `baseline-scripts/` | COT, ReAct, row-wise, voting, and batch runners |
| Analysis | `scripts/` | ROI, split, pressure, and visualization analysis |
| CMT2 | `pipelines/cmt2/` | Template/LLM generation, validation, and deduplication |
| Synthetic data | `pipelines/synthetic_data/synData/` | Synthetic sessions, question generation, and evaluation |
| Documentation | `docs/` | Architecture, contracts, provenance, and runbooks |
| Tests | `tests/`, `pipelines/cmt2/tests/` | Regression and pipeline tests |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set model credentials in the environment when a model-backed workflow is used:

```bash
export GEMINI_API_KEY='...'
export OPENAI_API_KEY='...'
```

No credentials are stored in QSTR. Rotate any credential previously present in
the source histories before using those providers.

## CMT2 quickstart

Run from `pipelines/cmt2/`:

```bash
python pipeline/run.py run \
  --templates template_q_param_cricket_pk.py \
  --matches-glob 'Cricket_tables/*.csv' \
  --out-dir output/dataset_runs/cmt2 \
  --max-matches 1 \
  --total-examples 10 \
  --seed 42
```

This performs generation, SQL/answer validation, and source/result
deduplication. See `pipelines/cmt2/README.md` for separate-stage commands and
CrewAI SQL/NL generation.

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
python -m unittest discover -s pipelines/cmt2/tests -p 'test_*.py'
```

The complete test suite requires the dependencies in `requirements.txt`.

## Provenance and artifacts

The original QSG refs and CMT2 commit are recorded in
`docs/qsg/branch-provenance.md`. Raw datasets, notebooks, and generated results
are intentionally not part of the initial QSTR commit. Their expected source
locations and handling rules are documented in `data/README.md` and
`artifacts/README.md`.
