# Outbreak Extraction

Following full text extraction, we use an LLM with tool calling to extract outbreak data. We extract concluded outbreaks that have defined temporal and geographical boundaries with reported epidemiological data.

## Workflow

The extraction follows a two-stage process:

1. **Screening**: Determine if the paper reports any concluded outbreaks (returns True/False)
2. **Extraction**: Extract structured outbreak data using tool calling (one call per distinct outbreak)

## Module Structure

```
outbreak_extraction/
├── run.py             # Main execution script with OutbreakExtractionRunner class
├── extractor.py       # OutbreakExtractor class with validation logic
├── tools.py           # Tool call definitions (OUTBREAK_TOOL_CALL)
└── prompts/
    ├── screening.md   # Screening prompt
    └── extraction.md  # Extraction prompt
```

## Key Extraction Rules

- Extract data exactly as stated in the paper (no calculations)
- Only extract duration if explicitly stated (never calculate from dates)
- Location fields must not contain commas
- Call extraction tool once per distinct outbreak
- Screen out ongoing outbreaks (extract concluded only)
- All case counts must be non-negative

## Data Fields

The extraction captures 30+ fields including:

- **Temporal**: start/end dates (day, month, year), duration, ongoing status
- **Location**: country (required), location, location type
- **Outbreak characteristics**: source, mode of detection, pre-outbreak status, case definition method
- **Case counts**: confirmed, probable, suspected, unspecified, asymptomatic, severe, deaths
- **Population**: geographic area population size, asymptomatic transmission described (required)
- **Sex disaggregation**: type of cases, male/female counts and proportions

## Output

- `{log_dir}/screening.jsonl` - All screening decisions
- `{log_dir}/extractions.jsonl` - All extraction attempts
- `{log_dir}/extracted_outbreaks.csv` - Final results (one row per outbreak)
