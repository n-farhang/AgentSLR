#!/usr/bin/env bash
# scripts/screening/run_abstract_screening.sh

set -euo pipefail

: <<'USAGE'
usage: run_abstract_screening.sh <pathogen> [data_dir] [model_name] [client_dir_name] [extra args...]

usage examples:
  5-row sample with OpenRouter + GLM 4.7 Flash
    scripts/screening/run_abstract_screening.sh lassa data/agentslr z-ai/glm-4.7-flash glm_4_7_flash \
      --base-url https://openrouter.ai/api/v1 \
      --api-key <OPENROUTER_API_KEY> \
      --article-doc-status metadata \
      --sample-size 5 --sample-seed 7

  Local vLLM example with a served model
    scripts/screening/run_abstract_screening.sh lassa data/agentslr openai/gpt-oss-20b gpt_oss_20b \
      --base-url http://localhost:6767/v1 \
      --api-key 6767 \
      --article-doc-status metadata

More examples: scripts/screening/README.md
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

PY_ARGS=(
  --stage abstract_screen
  --pathogen "$PATHOGEN"
  --data-dir "$DATA_DIR"
  --model-name "$MODEL_NAME"
  --log-level "$LOG_LEVEL"
  --reasoning-effort "$REASONING_EFFORT"
  --no-responses-api
)

[[ -n "$CLIENT_DIR_NAME" ]] && PY_ARGS+=(--client-dir-name "$CLIENT_DIR_NAME")

PY_ARGS+=("${EXTRA_ARGS[@]}")

python main.py "${PY_ARGS[@]}"
