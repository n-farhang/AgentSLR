#!/usr/bin/env bash
# scripts/harvest/run_full_harvest.sh
: <<'USAGE'
usage: run_full_harvest.sh <pathogen> [data_dir] [metadata_filename] [downloaded_filename]

usage examples:
  Default full harvest
    scripts/harvest/run_full_harvest.sh lassa data/agentslr

  Custom metadata and download filenames
    scripts/harvest/run_full_harvest.sh lassa data/testing lassa_metadata.csv lassa_downloads.csv

More examples: scripts/harvest/README.md
USAGE

set -euo pipefail

PATHOGEN="$1"
DATA_DIR="${2:-data/agentslr}"
HARVEST_METADATA_FILENAME="${3:-harvest_metadata.csv}"
HARVEST_DOWNLOADED_PDFS_FILENAME="${4:-harvest_downloaded_pdfs.csv}"

python main.py \
  --stage harvest \
  --pathogen "${PATHOGEN}" \
  --harvest-mode full \
  --data-dir "${DATA_DIR}" \
  --harvest-metadata-filename "${HARVEST_METADATA_FILENAME}" \
  --harvest-downloaded-pdfs-filename "${HARVEST_DOWNLOADED_PDFS_FILENAME}"
