# Harvest Stage

The harvest stage retrieves article metadata from bibliographic databases, deduplicates records and downloads PDFs from open-access sources.

## Data Sources

AgentSLR queries three bibliographic databases using domain-specific Boolean searches:

- **OpenAlex**: broad academic coverage with open metadata
- **PubMed**: biomedical literature via NCBI E-utilities
- **Europe PMC**: European biomedical repository with full-text links

## Workflow

1. **Metadata fetch**: query each database for the target pathogen
2. **Deduplication**: remove duplicate records using DOI and bibliographic matching
3. **PDF download**: retrieve full-text PDFs from open-access sources with caching and checkpointing

## Key Files

| File | Purpose |
|------|---------|
| `fetch_metadata.py` | Query databases and retrieve article metadata |
| `fetch_articles.py` | Download PDFs from open-access URLs |
| `queries.py` | Boolean search queries for each pathogen |
| `pipeline.py` | Orchestrates the harvest workflow |
| `common.py` | Shared utilities |

## Outputs

Outputs are written to `<data-dir>/harvests/<pathogen>/`:

| File | Description |
|------|-------------|
| `harvest_metadata.csv` | Deduplicated article metadata |
| `harvest_downloaded_pdfs.csv` | Download status and PDF paths |
| `pdfs/` | Downloaded PDF files |

## CLI Usage

```bash
# Full harvest (metadata + download)
python main.py --stage harvest --pathogen <pathogen> --data-dir <data-dir>

# Using shell wrapper
scripts/harvest/run_full_harvest.sh <pathogen> <data-dir>
```

See [`scripts/harvest/README.md`](../../scripts/harvest/README.md) for additional examples.

## Supported Pathogens

Marburg, Ebola, Lassa, SARS, Zika, MERS, Nipah, Rift Valley fever (rvf) and Crimean-Congo haemorrhagic fever (cchf).
