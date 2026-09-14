# Synthetic shopkeeper pipeline

This directory contains the compact `naman_syn_data` workflow. Run all commands
from the QSTR repository root so the examples are consistent.

## 1. Generate deterministic sessions

```bash
python pipelines/synthetic_data/synData/generate_op_sequence.py \
  --out-dir artifacts/runs/shopkeeper/sessions \
  --num-sessions 3 \
  --seed 12345
```

Importing `generate_op_sequence` is side-effect free. The CLI omits wall-clock
timestamps by default, making repeated runs with the same arguments
byte-for-byte reproducible. Add `--include-timestamp` only when needed.

## 2. Rebuild gold answers

```bash
python pipelines/synthetic_data/synData/generate_gold_qa.py \
  --sessions artifacts/runs/shopkeeper/sessions/sessions.jsonl \
  --output artifacts/runs/shopkeeper/gold_questions_answers.json
```

## 3. Run Gemini inference and evaluation

```bash
python -m pip install -e '.[synthetic]'
export GEMINI_API_KEY='...'
python pipelines/synthetic_data/synData/prompt_and_eval.py \
  --gold artifacts/runs/shopkeeper/gold_questions_answers.json \
  --experiment-dir artifacts/runs/shopkeeper/experiment
```

This writes per-question model logs and aggregate CSVs under `experiment/`.
Existing checked-in files are compact provenance fixtures; use
`artifacts/runs/` for new experiments.

## 4. Build the comparison view

```bash
python pipelines/synthetic_data/synData/generate_gold_pred_viz.py \
  --gold artifacts/runs/shopkeeper/gold_questions_answers.json \
  --experiment-dir artifacts/runs/shopkeeper/experiment \
  --output artifacts/runs/shopkeeper/gold_vs_predicted.html
```

`load_oolong.py` downloads Oolong datasets and therefore requires network
access and the `synthetic` installation profile.
