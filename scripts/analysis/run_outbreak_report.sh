#!/usr/bin/env bash
# scripts/analysis/run_outbreak_report.sh

set -euo pipefail

: <<'USAGE'
usage: run_outbreak_report.sh <pathogen> [data_dir] [client_dir_name] [extra args...]

This runs outbreak report generation for one client/pathogen pair.

usage examples:
  Raw report only
    scripts/analysis/run_outbreak_report.sh lassa data/agentslr gpt_4_1_mini \
      --writeup-mode raw

  Raw + LLM refinement
    scripts/analysis/run_outbreak_report.sh lassa data/agentslr gpt_4_1_mini \
      --writeup-mode both \
      --report-model-name gpt-5.4-mini
USAGE

PATHOGEN="$1"
DATA_DIR="${2:-data/agentslr}"

if [[ $# -ge 3 && "${3}" != --* ]]; then
  CLIENT_DIR_NAME="$3"
  EXTRA_ARGS=("${@:4}")
else
  CLIENT_DIR_NAME=""
  EXTRA_ARGS=("${@:3}")
fi

LOG_LEVEL="${LOG_LEVEL:-INFO}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

PY_ARGS=(
  --stage write_up_outbreaks
  --pathogen "$PATHOGEN"
  --data-dir "$DATA_DIR"
  --log-level "$LOG_LEVEL"
)

[[ -n "$CLIENT_DIR_NAME" ]] && PY_ARGS+=(--client-dir-name "$CLIENT_DIR_NAME")

PY_ARGS+=("${EXTRA_ARGS[@]}")

"$PYTHON_BIN" main.py "${PY_ARGS[@]}"
