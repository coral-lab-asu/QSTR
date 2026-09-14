# QSTR

QSTR is the consolidated knowledge-transfer repository for question, SQL, and
synthetic-data generation. It combines the reusable QSG code, the complete
CMT2 generation pipeline, and the synthetic-data work from `naman_syn_data` in
one fresh, credential-free history.

## Start here

QSTR requires Python 3.10 or newer. From a fresh clone:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python scripts/doctor.py
python -m pytest -q
```

For the exact core versions used by the KT verification:

```bash
python -m pip install -r requirements-core.lock
python -m pip install -e . --no-deps
```

For every workflow, including hosted models and legacy utilities:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

Fill only the credentials you need in `.env`, or export them in the shell.
`.env` is ignored by Git. No model credential is needed for the CMT2 smoke
test below.

## Credential-free CMT2 smoke test

Run this from the repository root:

```bash
python -m pipelines.cmt2.pipeline.run run \
  --templates pipelines/cmt2/examples/smoke_templates.py \
  --matches-glob 'pipelines/cmt2/examples/smoke_match.csv' \
  --out-dir artifacts/runs/cmt2-smoke \
  --max-matches 1 \
  --total-examples 3 \
  --seed 42
```

It exercises generation, SQL execution validation, invalid-record separation,
and answer-based deduplication. The expected result is three valid records and
two retained records because two templates intentionally produce the same
answer.

## Repository layout

| Area | Location | Purpose |
| --- | --- | --- |
| QSG core | `src/` | Dataset generation, inference, SQL agents, and evaluation |
| Baselines | `baseline-scripts/` | COT, ReAct, row-wise, voting, and batch runners |
| Analysis | `scripts/` | Analysis, visualization, export, and environment checks |
| CMT2 | `pipelines/cmt2/` | Generation, validation, deduplication, and CrewAI compatibility flows |
| Synthetic data | `pipelines/synthetic_data/synData/` | Session generation, gold answers, model evaluation, and compact fixtures |
| Documentation | `docs/` | Architecture, contracts, provenance, security, and KT runbook |
| Tests | `tests/`, `pipelines/cmt2/tests/` | QSG regression and CMT2 pipeline tests |

## Installation profiles

- `pip install -e .` installs deterministic generation, validation, and
  evaluation dependencies.
- `requirements-core.lock` pins the directly tested core package versions.
- `pip install -e '.[llm]'` adds hosted-model and CrewAI support.
- `pip install -e '.[synthetic]'` adds synthetic-data download and Gemini
  inference support.
- `pip install -e '.[local]'` adds the Transformers client; install the
  appropriate PyTorch build separately for your hardware.
- `pip install -r requirements.txt` installs all Python workflow dependencies.

GPU-specific runtimes are intentionally separate: install a PyTorch build that
matches the local CUDA stack for Transformers, and install `vllm` in the server
environment before using `run_vllm_server*.sh`.

Use `python scripts/doctor.py --require-llm` before a hosted-model run. The
doctor reports whether credentials are present but never displays their values.

## Data and artifacts

The paper-facing cricket release is versioned under `data/`: 638 source
tables, 121 hand-authored seeds, 4,256 generated queries, and their historical
ground-truth enrichment. Verify it with:

```bash
python scripts/verify_cricket_release.py
```

Read the [cricket data card](data/README.md) and the
[reproduction runbook](docs/cricket-reproduction.md) before running an
experiment. New generated runs, model outputs, notebooks, and result trees
belong under `artifacts/runs/` and remain ignored. Compact synthetic fixtures
from `naman_syn_data` are also retained as examples and provenance.

The [verification record](docs/verification.md) distinguishes release integrity,
SQL/answer checks, and the workflows actually tested. Historical ground truth
includes known unresolved records and answer mismatches.

Continue with the [KT runbook](docs/kt-runbook.md), the
[CMT2 guide](pipelines/cmt2/README.md), and the
[repository map](docs/repository-map.md).

The included GitHub Actions workflow repeats the credential-free core checks
on Python 3.10 and 3.12 for every push and pull request.
