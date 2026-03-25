#!/usr/bin/env bash
# scripts/extraction/run_model_extraction.sh

set -euo pipefail

: <<'USAGE'
usage: run_model_extraction.sh <pathogen> [data_dir] [model_name] [client_dir_name] [extra args...]

This runs model extraction from the fulltext screening output for one client/pathogen pair.

usage examples:
  5-row sample with GPT-5.4 Mini
    scripts/extraction/run_model_extraction.sh lassa data/agentslr gpt-5.4-mini gpt_5_4_mini \
      --sample-size 5 --sample-seed 7

  Local vLLM example with a served model
    scripts/extraction/run_model_extraction.sh lassa data/agentslr openai/gpt-oss-20b gpt_oss_20b \
      --base-url http://localhost:6767/v1 \
      --api-key 6767 \
      --sample-size 5 --sample-seed 7
USAGE

PATHOGEN="$1"
DATA_DIR="${2:-data/agentslr}"
MODEL_NAME="${3:-gpt-4.1-mini}"

if [[ $# -ge 4 && "${4}" != --* ]]; then
  CLIENT_DIR_NAME="$4"
  EXTRA_ARGS=("${@:5}")
else
  CLIENT_DIR_NAME=""
  EXTRA_ARGS=("${@:4}")
fi

LOG_LEVEL="${LOG_LEVEL:-INFO}"
REASONING_EFFORT="${REASONING_EFFORT:-high}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

PY_ARGS=(
  --stage data_extraction_models
  --pathogen "$PATHOGEN"
  --data-dir "$DATA_DIR"
  --model-name "$MODEL_NAME"
  --log-level "$LOG_LEVEL"
  --reasoning-effort "$REASONING_EFFORT"
  --no-responses-api
)

[[ -n "$CLIENT_DIR_NAME" ]] && PY_ARGS+=(--client-dir-name "$CLIENT_DIR_NAME")

PY_ARGS+=("${EXTRA_ARGS[@]}")

"$PYTHON_BIN" main.py "${PY_ARGS[@]}"
