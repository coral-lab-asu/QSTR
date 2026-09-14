#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
PYTHON_BIN="${PYTHON_BIN:-python}"
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "GEMINI_API_KEY must be set in the environment before running this script." >&2
  exit 1
fi
cd "${ROOT_DIR}"

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "GEMINI_API_KEY is not set. Export it before running this script."
  exit 1
fi

MODEL="${MODEL:-gemini-2.5-flash}"
PROVIDER="${PROVIDER:-gemini}"
DATASET="${DATASET:-dataset-cricket/cricket-overall.json}"
N_SAMPLES="${N_SAMPLES:-5}"
SEED="${SEED:-0}"
WORKERS="${WORKERS:-8}"
MAX_RETRIES="${MAX_RETRIES:-3}"
SCVOTE_NUM_VOTES="${SCVOTE_NUM_VOTES:-5}"
RUN_TAG="${RUN_TAG:-gemini_smoke_main_$(date +%Y%m%d_%H%M%S)}"

run_baseline() {
  local script_name="$1"
  shift
  local baseline_name="${script_name%.py}"
  local out_dir=""
  local log_dir=""
  local out_file=""
  local summary_file=""

  case "${script_name}" in
    "COT.py")
      out_dir="baseline-results/${MODEL}/COT"
      ;;
    "RowCOT.py")
      out_dir="baseline-results/${MODEL}/ROW_COT"
      ;;
    "ReAct.py")
      out_dir="baseline-results/${MODEL}/REACT"
      ;;
    "OnePassCOT.py")
      out_dir="baseline-results/${MODEL}/ONEPASS_COT"
      ;;
    "SCVote.py")
      out_dir="baseline-results/${MODEL}/SC_VOTE/${SCVOTE_NUM_VOTES}"
      ;;
    *)
      echo "Unknown baseline script: ${script_name}"
      exit 1
      ;;
  esac

  log_dir="${out_dir}/logs"
  out_file="${out_dir}/predictions.jsonl"
  summary_file="${out_dir}/summary.json"

  echo
  echo "============================================================"
  echo "Running ${script_name} on first ${N_SAMPLES} main-dataset samples"
  echo "Model: ${MODEL}"
  echo "Run tag: ${RUN_TAG}"
  echo "Output dir: ${out_dir}"
  echo "============================================================"

  "${PYTHON_BIN}" "${ROOT_DIR}/baseline-scripts/${script_name}" \
    --provider "${PROVIDER}" \
    --model "${MODEL}" \
    --api-key "${GEMINI_API_KEY}" \
    --dataset "${DATASET}" \
    --n "${N_SAMPLES}" \
    --seed "${SEED}" \
    --workers "${WORKERS}" \
    --max-retries "${MAX_RETRIES}" \
    --log-dir "${log_dir}" \
    --out "${out_file}" \
    --summary-out "${summary_file}" \
    --run-id "${RUN_TAG}_${script_name%.py}" \
    "$@"
}

run_baseline "COT.py"
run_baseline "RowCOT.py"
run_baseline "ReAct.py"
run_baseline "OnePassCOT.py"
run_baseline "SCVote.py" --num-votes "${SCVOTE_NUM_VOTES}"

echo
echo "All Gemini smoke-test baselines completed."
