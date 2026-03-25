# Extraction Stage

The extraction stage uses LLM tool-calling to extract structured epidemiological data from full-text articles that passed screening.

## Data Categories

AgentSLR extracts three categories of structured data:

| Category | Description | Output |
|----------|-------------|--------|
| **Parameters** | Epidemiological parameters (reproduction number, severity, seroprevalence, etc.) | `data_extraction_parameters.jsonl` |
| **Models** | Transmission and modelling study information | `data_extraction_models.csv` |
| **Outbreaks** | Outbreak event information (geography, dates, case counts) | `data_extraction_outbreaks.csv` |

## Workflow

For each data category, extraction follows a two-stage process:

1. **Presence flagging**: identify articles containing relevant data for extraction
2. **Targeted extraction**: extract structured fields using schema-validated tool calls

## Parameter Classes

Parameter extraction is organised around 8 implemented parameter classes:

| PERG Parameter Class | Implementation |
|---------------------|----------------|
| Attack rate | `parameters/extraction/tools/attack_rate/` |
| Growth rate | `parameters/extraction/tools/growth_rate/` |
| Human delay | `parameters/extraction/tools/human_delay/` |
| Mutations | `parameters/extraction/tools/mutation_rate/` |
| Relative contribution | `parameters/extraction/tools/relative_contribution/` |
| Reproduction number | `parameters/extraction/tools/reproduction_number/` |
| Seroprevalence | `parameters/extraction/tools/seroprevalence/` |
| Severity | `parameters/extraction/tools/severity/` |

See [`parameters/extraction/README.md`](parameters/extraction/README.md) for detailed parameter class documentation.

## Key Files

| File | Purpose |
|------|---------|
| `run.py` | Extraction orchestration |
| `common.py` | Shared extraction utilities |
| `parameters/` | Parameter extraction logic and tools |
| `models/` | Model extraction logic |
| `outbreaks/` | Outbreak extraction logic |

## Outputs

Outputs are written to `<data-dir>/client/<client-dir-name>/<pathogen>/extractions/`:

| File | Description |
|------|-------------|
| `data_extraction_parameters.jsonl` | Extracted epidemiological parameters |
| `data_extraction_models.csv` | Extracted model information |
| `data_extraction_outbreaks.csv` | Extracted outbreak information |

## CLI Usage

```bash
# Parameter extraction
python main.py --stage data_extraction_parameters \
  --pathogen <pathogen> \
  --data-dir <data-dir> \
  --model-name <model-name> \
  --client-dir-name <client-dir-name>

# Model extraction
python main.py --stage data_extraction_models \
  --pathogen <pathogen> \
  --data-dir <data-dir> \
  --model-name <model-name> \
  --client-dir-name <client-dir-name>

# Outbreak extraction
python main.py --stage data_extraction_outbreaks \
  --pathogen <pathogen> \
  --data-dir <data-dir> \
  --model-name <model-name> \
  --client-dir-name <client-dir-name>
```

See [`scripts/extraction/README.md`](../../scripts/extraction/README.md) for additional examples.

## API Variants

Extraction supports both standard Chat Completions and Responses API modes:

- `extraction/`: standard tool-calling
- `extraction_responses_api/`: OpenAI Responses API format
