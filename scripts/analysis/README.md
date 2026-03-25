# Analysis Scripts

These scripts wrap `python main.py` for the report-generation stages.

## Parameter Report

`run_parameter_report.sh` runs parameter report generation from the current client's parameter extraction outputs.

### Raw report only
```bash
scripts/analysis/run_parameter_report.sh \
  <pathogen> <data-dir> <client-dir-name> \
  --writeup-mode raw
```

### Raw + LLM refinement
```bash
scripts/analysis/run_parameter_report.sh \
  <pathogen> <data-dir> <client-dir-name> \
  --writeup-mode both \
  --report-model-name <report-model-name> \
  --report-base-url https://api.openai.com/v1
```

## Model Report

`run_model_report.sh` runs model report generation from the current client's model extraction outputs.

### Raw report only
```bash
scripts/analysis/run_model_report.sh \
  <pathogen> <data-dir> <client-dir-name> \
  --writeup-mode raw
```

### Local vLLM or other custom endpoint
```bash
scripts/analysis/run_model_report.sh \
  <pathogen> <data-dir> <client-dir-name> \
  --writeup-mode llm \
  --report-model-name <model-name> \
  --report-base-url http://localhost:6767/v1 \
  --report-api-key 6767 \
  --no-report-responses-api
# e.g. --report-model-name gpt-oss-120b
```

## Outbreak Report

`run_outbreak_report.sh` runs outbreak report generation from the current client's outbreak extraction outputs.

### Raw report only
```bash
scripts/analysis/run_outbreak_report.sh \
  <pathogen> <data-dir> <client-dir-name> \
  --writeup-mode raw
```

### Raw + LLM refinement
```bash
scripts/analysis/run_outbreak_report.sh \
  <pathogen> <data-dir> <client-dir-name> \
  --writeup-mode both \
  --report-model-name <report-model-name> \
  --report-reasoning-effort high
```

## Notes

- All three scripts pass through extra CLI args to `main.py`.
- `--writeup-mode raw`, `--writeup-mode llm` and `--writeup-mode both` are all supported.
- Use `--report-model-name`, `--report-base-url`, `--report-api-key` and related `--report-*` flags when the refinement model should differ from the extraction model.
