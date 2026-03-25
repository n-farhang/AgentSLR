#!/usr/bin/env bash

set -euo pipefail

: <<'USAGE'
usage: run_all_stages.sh <pathogen> [data_dir] [model_name] [client_dir_name] [extra args...]

This runs `python main.py --stage run_all` with the same positional wrapper style
as the other scripts.

Pipeline control:
  --resume-from <stage>   Resume from a particular stage and run the rest.

Examples:
  Full pipeline with local vLLM using the old served defaults
    scripts/pipeline/run_all_stages.sh lassa data/agentslr openai/gpt-oss-120b gpt_oss_120b \
      --base-url http://localhost:6767/v1 \
      --api-key 6767 \
      --ocr-client mistral \
      --config-json config.json

  Resume from full-text screening onward
    scripts/pipeline/run_all_stages.sh lassa data/agentslr openai/gpt-oss-120b gpt_oss_120b \
      --resume-from fulltext_screen \
      --base-url http://localhost:6767/v1 \
      --api-key 6767

  Local OCR with a dedicated OCR Python
    OCR_PYTHON_BIN=.venv-ocr/bin/python \
    scripts/pipeline/run_all_stages.sh lassa data/agentslr gpt-5.4-mini gpt_5_4_mini \
      --ocr-client glm \
      --ocr-device auto \
      --config-json config.json

  Alternative model on vLLM
    # scripts/pipeline/run_all_stages.sh lassa data/agentslr moonshotai/Kimi-K2.5 kimi_k2_5 \
    #   --base-url http://localhost:6767/v1 \
    #   --api-key 6767 \
    #   --ocr-client mistral \
    #   --config-json config.json
USAGE

print_usage() {
  sed -n '2,999p' "$0" | sed -n '/^: <<'"'"'USAGE'"'"'$/,/^USAGE$/p' | sed '1d;$d'
}

if [[ $# -lt 1 ]]; then
  print_usage >&2
  exit 1
fi

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  print_usage
  exit 0
fi

PATHOGEN="$1"
DATA_DIR="${2:-data/agentslr}"
MODEL_NAME="${3:-gpt-4.1-mini}"

if [[ $# -ge 4 && "${4}" != --* ]]; then
  CLIENT_DIR_NAME="$4"
  if [[ $# -ge 5 ]]; then
    EXTRA_ARGS=("${@:5}")
  else
    EXTRA_ARGS=()
  fi
else
  CLIENT_DIR_NAME=""
  if [[ $# -ge 4 ]]; then
    EXTRA_ARGS=("${@:4}")
  else
    EXTRA_ARGS=()
  fi
fi

LOG_LEVEL="${LOG_LEVEL:-INFO}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

PY_ARGS=(
  main.py
  --stage run_all
  --pathogen "$PATHOGEN"
  --data-dir "$DATA_DIR"
  --model-name "$MODEL_NAME"
  --log-level "$LOG_LEVEL"
)

if [[ -n "$CLIENT_DIR_NAME" ]]; then
  PY_ARGS+=(--client-dir-name "$CLIENT_DIR_NAME")
fi

if [[ -n "${OCR_PYTHON_BIN:-}" ]]; then
  PY_ARGS+=(--ocr-python-bin "$OCR_PYTHON_BIN")
fi

PY_ARGS+=("${EXTRA_ARGS[@]}")

"$PYTHON_BIN" "${PY_ARGS[@]}"
