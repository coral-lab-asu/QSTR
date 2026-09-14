# Knowledge-transfer runbook

This is the operational handoff for a new QSTR maintainer.

## First 15 minutes

1. Use Python 3.10 or newer and create a virtual environment.
2. Install `pip install -e '.[dev]'` for core work, or
   `pip install -r requirements.txt` for every workflow.
3. Copy `.env.example` to `.env`; fill only the providers you intend to call.
4. Run `python scripts/doctor.py` and `python -m pytest -q`.
5. Run the credential-free CMT2 smoke command from the root README.

A successful smoke run reports three valid records, zero invalid records, and
two retained records after deduplication.

Use `requirements-core.lock` followed by `pip install -e . --no-deps` when an
exactly matched core environment is more important than accepting newer
compatible package versions.

## Capability map

| Goal | Canonical entry point | Inputs | Outputs |
| --- | --- | --- | --- |
| Generate and curate CMT2 data | `python -m pipelines.cmt2.pipeline.run run` | template files and match CSVs | generated, validation, invalid, deduped, removal, and manifest files |
| Generate QSG coverage data | `python -m src.core.generate_questions --help` | converted templates and cricket CSVs | coverage JSON/parts and summaries |
| Generate split/provenance data | `python -m src.core.generate_questions_split --help` | templates and match CSVs | split datasets and provenance metadata |
| Run baseline inference | `baseline-scripts/*.py --help` | dataset plus provider/model configuration | predictions, per-sample logs, and summaries |
| Evaluate predictions | `src/eval/` and `baseline-scripts/eval_*.py` | datasets and predictions | samplewise and aggregate metrics |
| Generate shopkeeper sessions | `generate_op_sequence.py` | seed and session count | session JSONL and transcripts |

## Data contract

Canonical generated records use SQL table name `df` and should include
`record_id`, source path, template identity, question, SQL, parameters, and an
answer object with `columns` and `rows`. See `docs/qsg/data-contracts.md` for
the full compatibility contract.

Do not commit large source tables or new run outputs. Put source data in
`data/raw/` and outputs in `artifacts/runs/`. Preserve the generated
`run_manifest.json` whenever an experiment is archived externally.

## Provider configuration

- Gemini: `GEMINI_API_KEY` (the synthetic client also accepts `GOOGLE_API_KEY`)
- OpenAI: `OPENAI_API_KEY`, optionally `OPENAI_BASE_URL`
- DeepInfra: `DEEPINFRA_API_KEY`, optionally `DEEPINFRA_BASE_URL`
- Gated Hugging Face models: `HF_TOKEN`

Never pass real credentials in committed command files. Prefer environment
resolution over `--api-key`, because command-line arguments may be visible to
other processes on shared machines.

## Reproducibility checklist

- Pin the QSTR commit, require `qstr_worktree_dirty: false`, and preserve
  `run_manifest.json`.
- Preserve the exact command, seed, model name, and provider.
- Record input checksums and licensing/source metadata.
- Keep source paths stable when comparing deterministic record IDs.
- Report parser/validation failures separately from model-quality metrics.
- Compare models on the same evaluable sample subset.

## Common failures

- `ModuleNotFoundError`: run the appropriate installation profile and rerun
  `scripts/doctor.py`.
- `No match CSV files found`: quote the glob and verify it from the repository
  root.
- Validation returns status 1: inspect `validation.no_overs.json` and
  `dataset.no_overs.invalid.json`; do not promote invalid records.
- Missing provider key: copy `.env.example` to `.env` or export the variable.
- CUDA/vLLM startup failure: override `CUDA_VISIBLE_DEVICES`, `MODEL`, `PORT`,
  cache, tensor-parallel, and memory settings in the environment.
- `vllm: command not found`: install vLLM separately in the GPU-serving
  environment; it is intentionally not part of the cross-platform Python
  requirements.

## Before pushing or releasing

Run:

```bash
python scripts/doctor.py
python -m pytest -q
python -m compileall -q src pipelines scripts baseline-scripts
bash -n run_gemini_smoke_main.sh run_vllm_server.sh run_vllm_server_2.sh
git diff --check
```

Also scan the current tree and Git history for credentials. If a real key was
ever committed, revoke it first; deleting it from the latest file does not
invalidate the exposed credential.
