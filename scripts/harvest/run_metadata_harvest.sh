#!/usr/bin/env bash
# scripts/harvest/run_metadata_harvest.sh
: <<'USAGE'
usage: run_metadata_harvest.sh <pathogen> [data_dir] [metadata_filename]

usage examples:
  Default metadata harvest
    scripts/harvest/run_metadata_harvest.sh lassa data/agentslr

  Custom output filename
    scripts/harvest/run_metadata_harvest.sh lassa data/testing lassa_metadata.csv

More examples: scripts/harvest/README.md
USAGE

set -euo pipefail

PATHOGEN="$1"
DATA_DIR="${2:-data/agentslr}"
HARVEST_METADATA_FILENAME="${3:-harvest_metadata.csv}"

python main.py \
  --stage harvest \
  --pathogen "${PATHOGEN}" \
  --harvest-mode metadata_only \
  --data-dir "${DATA_DIR}" \
  --harvest-metadata-filename "${HARVEST_METADATA_FILENAME}"
