# Screening Stage

The screening stage filters articles using LLM-based title/abstract screening and full-text screening, applying predefined inclusion and exclusion criteria.

## Screening Modes

### Title and Abstract Screening

Initial screening based on article titles and abstracts. The LLM evaluates each article against five components following the ScreenPrompt methodology:

1. Study objectives
2. Inclusion/exclusion criteria
3. Chain-of-thought reasoning instructions
4. Article abstract
5. Structured output format

### Full-text Screening

Stricter screening applied to OCR-converted article text. Requires extractable quantitative epidemiological parameters (e.g. transmission rates, incubation periods, severity outcomes) while excluding literature reviews, meta-analyses and case studies with fewer than 10 infected individuals.

## Input Sources

The `--article-doc-status` argument controls which input file is used:

| Value | Input Source |
|-------|--------------|
| `metadata` | `harvest_metadata.csv` |
| `download` | `harvest_downloaded_pdfs.csv` |
| `ocr_markdown` | `articles_with_markdown.csv` |

## Key Files

| File | Purpose |
|------|---------|
| `abstract.py` | Title/abstract screening logic |
| `fulltext.py` | Full-text screening logic |
| `prompts.py` | Screening prompt templates |
| `common.py` | Shared screening utilities |
| `prompt_templates/` | Detailed prompt templates |

## Outputs

Outputs are written to `<data-dir>/client/<client-dir-name>/<pathogen>/screening/`:

| File | Description |
|------|-------------|
| `abstract_screening.csv` | Abstract screening decisions |
| `fulltext_screening.csv` | Full-text screening decisions |

## CLI Usage

```bash
# Abstract screening
python main.py --stage abstract_screen \
  --pathogen <pathogen> \
  --data-dir <data-dir> \
  --model-name <model-name> \
  --client-dir-name <client-dir-name>

# Full-text screening
python main.py --stage fulltext_screen \
  --pathogen <pathogen> \
  --data-dir <data-dir> \
  --model-name <model-name> \
  --client-dir-name <client-dir-name> \
  --fulltext-screening-mode direct_fulltext
```

See [`scripts/screening/README.md`](../../scripts/screening/README.md) for additional examples.

## Full-text Screening Modes

| Mode | Description |
|------|-------------|
| `direct_fulltext` | Screen all articles with OCR markdown |
| `on_ai4epi_abstracts` | Only screen articles that passed AI abstract screening |
| `on_perg_abstracts` | Only screen articles that passed PERG abstract screening |
