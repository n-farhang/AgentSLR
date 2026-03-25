#!/usr/bin/env bash
# scripts/serve_vllm/serve_client.sh

set -euo pipefail

# Default local serving config used by the pipeline examples:
#   scripts/pipeline/run_all_stages.sh lassa data/agentslr openai/gpt-oss-120b gpt_oss_120b \
#     --base-url http://localhost:6767/v1 \
#     --api-key 6767
#
# Alternative Moonshot example:
#   MODEL_NAME="moonshotai/Kimi-K2.5"
#   TP_SIZE=8
#   EXTRA_VLLM_ARGS=(
#     --async-scheduling
#     --mm-encoder-tp-mode data
#     --tool-call-parser kimi_k2
#     --enable-auto-tool-choice
#     --reasoning-parser kimi_k2
#     --trust-remote-code
#   )

PORT=6767
API_KEY="6767"
MODEL_NAME="openai/gpt-oss-120b"
GPU_IDS="0,1"
TP_SIZE=1
EXTRA_VLLM_ARGS=(
  --max-model-len 131072
  --async-scheduling
)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --api-key)
      API_KEY="$2"
      shift 2
      ;;
    --model-name)
      MODEL_NAME="$2"
      shift 2
      ;;
    --gpu-ids)
      GPU_IDS="$2"
      shift 2
      ;;
    --tp-size)
      TP_SIZE="$2"
      shift 2
      ;;
    --extra-vllm-arg)
      EXTRA_VLLM_ARGS+=("$2")
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/serve_vllm/serve_client.sh [options]

Options:
  --port PORT
  --api-key KEY
  --model-name MODEL
  --gpu-ids IDS
  --tp-size SIZE
  --extra-vllm-arg ARG
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

CUDA_VISIBLE_DEVICES="${GPU_IDS}" \
vllm serve "${MODEL_NAME}" \
  --port "${PORT}" \
  --api-key "${API_KEY}" \
  --tensor-parallel-size "${TP_SIZE}" \
  "${EXTRA_VLLM_ARGS[@]}"

echo "Serving ${MODEL_NAME} on port ${PORT} with GPU IDs: ${GPU_IDS}"
