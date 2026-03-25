#!/usr/bin/env bash
# scripts/harvest/run_download_harvest.sh
: <<'USAGE'
usage: run_download_harvest.sh <pathogen> [data_dir] [metadata_filename] [downloaded_filename] [metadata_input]

usage examples:
  Download PDFs using the default harvest metadata file
    scripts/harvest/run_download_harvest.sh lassa data/agentslr

  Download PDFs from a custom metadata CSV
    scripts/harvest/run_download_harvest.sh lassa data/testing harvest_metadata.csv harvest_downloaded_pdfs.csv /absolute/path/to/metadata.csv

More examples: scripts/harvest/README.md
USAGE

set -euo pipefail

PATHOGEN="$1"
DATA_DIR="${2:-data/agentslr}"
HARVEST_METADATA_FILENAME="${3:-harvest_metadata.csv}"
HARVEST_DOWNLOADED_PDFS_FILENAME="${4:-harvest_downloaded_pdfs.csv}"
METADATA_INPUT="${5:-}"

if [[ -n "${METADATA_INPUT}" ]]; then
  python main.py \
    --stage harvest \
    --pathogen "${PATHOGEN}" \
    --harvest-mode download_only \
    --data-dir "${DATA_DIR}" \
    --harvest-metadata-filename "${HARVEST_METADATA_FILENAME}" \
    --harvest-downloaded-pdfs-filename "${HARVEST_DOWNLOADED_PDFS_FILENAME}" \
    --metadata-input "${METADATA_INPUT}"
else
  python main.py \
    --stage harvest \
    --pathogen "${PATHOGEN}" \
    --harvest-mode download_only \
    --data-dir "${DATA_DIR}" \
    --harvest-metadata-filename "${HARVEST_METADATA_FILENAME}" \
    --harvest-downloaded-pdfs-filename "${HARVEST_DOWNLOADED_PDFS_FILENAME}"
fi
