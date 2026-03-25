# Extraction Scripts

These scripts wrap `python main.py` for the extraction stages.

## Parameter Extraction

`run_parameter_extraction.sh` runs structured epidemiological parameter extraction from the current client's `fulltext_screening.csv`. Use it when you want parameter-class outputs such as severity, seroprevalence and reproduction number.

### Default parameter extraction
```bash
scripts/extraction/run_parameter_extraction.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name>
```

### 5-row smoke test
```bash
scripts/extraction/run_parameter_extraction.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --sample-size 5 --sample-seed 7
```

### Restrict to PERG-included full-text rows
```bash
scripts/extraction/run_parameter_extraction.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --perg-subset
```

### Local vLLM server
```bash
scripts/extraction/run_parameter_extraction.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --base-url http://localhost:6767/v1 \
  --api-key 6767
# e.g. lassa data/agentslr gpt-oss-120b gpt_oss_120b
```

## Model Extraction

`run_model_extraction.sh` runs structured transmission-model extraction from the current client's `fulltext_screening.csv`. Use it when you want model metadata such as model type, assumptions and code availability.

### Default model extraction
```bash
scripts/extraction/run_model_extraction.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name>
```

### 5-row smoke test
```bash
scripts/extraction/run_model_extraction.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --sample-size 5 --sample-seed 7
```

### Local vLLM server
```bash
scripts/extraction/run_model_extraction.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --base-url http://localhost:6767/v1 \
  --api-key 6767
```

## Outbreak Extraction

`run_outbreak_extraction.sh` runs structured outbreak extraction from the current client's `fulltext_screening.csv`. Use it when you want outbreak-level metadata such as geography, dates and case counts.

### Default outbreak extraction
```bash
scripts/extraction/run_outbreak_extraction.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name>
```

### 5-row smoke test
```bash
scripts/extraction/run_outbreak_extraction.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --sample-size 5 --sample-seed 7
```

### Local vLLM server
```bash
scripts/extraction/run_outbreak_extraction.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --base-url http://localhost:6767/v1 \
  --api-key 6767
```

## Notes

- All three scripts read from the current client's `screening/fulltext_screening.csv`.
- `--sample-size` and `--sample-seed` are supported for quick smoke tests.
- `--perg-subset` is available for extraction runs that should use only rows with `perg_fulltext_result == INCLUDE`.
- `--use-guided-json` can be passed through for guided JSON extraction runners.
