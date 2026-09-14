#!/usr/bin/env bash
set -euo pipefail

# Override these environment variables for a machine-specific deployment.
CACHE_ROOT="${HF_CACHE_ROOT:-${XDG_CACHE_HOME:-$PWD/.cache}/huggingface}"
export HF_HOME="${HF_HOME:-$CACHE_ROOT}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME}"
export HF_DATASETS_CACHE="${HF_DATASETS_CACHE:-$HF_HOME}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-4,5}"

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "HF_TOKEN must be set for gated Hugging Face models." >&2
  exit 1
fi

MODEL="${MODEL:-meta-llama/Llama-3.3-70B-Instruct}"
PORT="${PORT:-8002}"

exec vllm serve "$MODEL" \
  --max-model-len "${MAX_MODEL_LEN:-32768}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION:-0.8}" \
  --max-num-seqs "${MAX_NUM_SEQS:-64}" \
  --tensor-parallel-size "${TENSOR_PARALLEL_SIZE:-2}" \
  --port "$PORT"
