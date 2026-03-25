# Harvest Scripts

These scripts wrap `python main.py --stage harvest` for the three harvest modes.

## Metadata Harvest

`run_metadata_harvest.sh` fetches and deduplicates article metadata only. Use it when you want a fresh `harvest_metadata.csv` without downloading PDFs yet.

### Default metadata harvest
```bash
scripts/harvest/run_metadata_harvest.sh \
  <pathogen> <data-dir>
# e.g. lassa data/agentslr
```

### Custom output filename
```bash
scripts/harvest/run_metadata_harvest.sh \
  <pathogen> <data-dir> <output-filename>
# e.g. lassa data/testing lassa_metadata.csv
```

## Full Harvest

`run_full_harvest.sh` runs the end-to-end harvest flow. It fetches metadata first and then downloads PDFs into the harvest directory.

### Default full harvest
```bash
scripts/harvest/run_full_harvest.sh \
  <pathogen> <data-dir>
# e.g. lassa data/agentslr
```

### Custom metadata and download filenames
```bash
scripts/harvest/run_full_harvest.sh \
  <pathogen> <data-dir> <metadata-filename> <downloads-filename>
# e.g. lassa data/testing lassa_metadata.csv lassa_downloads.csv
```

## Download-Only Harvest

`run_download_harvest.sh` skips metadata fetching and only performs the PDF download step. Use it when you already have a metadata CSV and want to resume or rerun downloads.

### Download PDFs using the default metadata file
```bash
scripts/harvest/run_download_harvest.sh \
  <pathogen> <data-dir>
```

### Download PDFs from a custom metadata CSV
```bash
scripts/harvest/run_download_harvest.sh \
  <pathogen> <data-dir> <metadata-filename> <downloads-filename> <input-csv-path>
# e.g. lassa data/testing harvest_metadata.csv harvest_downloaded_pdfs.csv /path/to/metadata.csv
```
