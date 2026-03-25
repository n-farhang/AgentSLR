# Screening Scripts

These scripts are thin wrappers around `python main.py` for the screening stages.

## Abstract Screening

`run_abstract_screening.sh` runs title and abstract screening. It can read from harvest metadata, download-level harvest outputs or OCR markdown outputs depending on `--article-doc-status`.

### Metadata input + Chat Completions
```bash
scripts/screening/run_abstract_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --article-doc-status metadata
```

### Downloaded harvest CSV + Chat Completions
```bash
scripts/screening/run_abstract_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --article-doc-status download
```

### OCR markdown input + Responses API
```bash
scripts/screening/run_abstract_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --article-doc-status ocr_markdown \
  --responses-api
```

### Custom input CSV override
```bash
scripts/screening/run_abstract_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --screening-input /absolute/path/to/input.csv \
  --article-doc-status metadata
```

### 5-row smoke test
```bash
scripts/screening/run_abstract_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --article-doc-status metadata \
  --sample-size 5 --sample-seed 7
```

### OpenRouter
```bash
scripts/screening/run_abstract_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --base-url https://openrouter.ai/api/v1 \
  --api-key <OPENROUTER_API_KEY> \
  --article-doc-status metadata
```

### Local vLLM server
```bash
scripts/screening/run_abstract_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --base-url http://localhost:1738/v1 \
  --api-key 1738 \
  --article-doc-status metadata
# e.g. lassa data/agentslr gpt-oss-120b gpt_oss_120b
```

## Full-Text Screening

`run_fulltext_screening.sh` runs screening over `articles_with_markdown.csv`. It supports direct full-text review, conditioning on AI abstract decisions or conditioning on PERG abstract decisions.

### Direct full-text + Chat Completions
```bash
scripts/screening/run_fulltext_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --fulltext-screening-mode direct_fulltext
```

### Condition on AI abstract decisions
```bash
scripts/screening/run_fulltext_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --fulltext-screening-mode on_ai4epi_abstracts
```

### Condition on PERG abstract decisions
```bash
scripts/screening/run_fulltext_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --fulltext-screening-mode on_perg_abstracts
```

### Direct full-text + Responses API
```bash
scripts/screening/run_fulltext_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --fulltext-screening-mode direct_fulltext \
  --responses-api
```

### Custom markdown CSV override
```bash
scripts/screening/run_fulltext_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --fulltext-screening-mode direct_fulltext \
  --screening-input /absolute/path/to/articles_with_markdown.csv
```

### 5-row smoke test
```bash
scripts/screening/run_fulltext_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --fulltext-screening-mode direct_fulltext \
  --sample-size 5 --sample-seed 7
```

### OpenRouter
```bash
scripts/screening/run_fulltext_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --base-url https://openrouter.ai/api/v1 \
  --api-key <OPENROUTER_API_KEY> \
  --fulltext-screening-mode direct_fulltext
```

### Local vLLM server
```bash
scripts/screening/run_fulltext_screening.sh \
  <pathogen> <data-dir> <model-name> <client-dir-name> \
  --base-url http://localhost:1738/v1 \
  --api-key 1738 \
  --fulltext-screening-mode direct_fulltext
```
