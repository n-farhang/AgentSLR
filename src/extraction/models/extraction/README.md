# Model Extraction

Following full text extraction, we use an LLM with tool calling to extract model characteristics. We only extract dynamic transmission models (compartmental, branching process, agent-based, etc.), not regression-only forecasting analyses.

## Workflow

The extraction follows a two-stage process:

1. **Screening**: Determine if the paper uses dynamic transmission models (returns True/False)
2. **Extraction**: Extract structured model characteristics using tool calling (one call per paper captures ALL models)

## Module Structure

```
model_extraction/
├── run.py             # Main execution script with ModelExtractionRunner class
├── extractor.py       # ModelExtractor class with validation logic
├── tools.py           # Tool call definitions (MODEL_TOOL_CALL)
└── prompts/
    ├── screening.md   # Screening prompt
    └── extraction.md  # Extraction prompt
```

## Key Extraction Rules

- Single tool call per paper (captures all models using multi-select arrays)
- Only extract stochastic/deterministic if explicitly stated
- Prefer existing options over "Other"
- Extract everything as presented (even suspected errors)
- If "Not compartmental" selected, no other compartmental types allowed

## Data Fields

The extraction captures comprehensive model characteristics:

- **Core model type**: model_type, compartmental_type (multi-select), stoch_deter
- **Model features**: transmission_route (multi-select), uncertainty_considered, spatial_model, spillover_included
- **Assumptions** (multi-select): homogeneous mixing, latent=incubation, heterogeneity types, age-dependent susceptibility, cross-immunity
- **Model fitting**: theoretical_model (true = not fitted to data, false = fitted to data)
- **Interventions** (multi-select): vaccination, quarantine, vector control, treatment, contact tracing, etc.
- **Code availability**: code_available (required), coding_language (multi-select), data_available, readme_included

## Multi-Select Field Format

- Passed to tool as arrays: `["Vaccination", "Quarantine"]`
- Stored in CSV as semicolon-separated: `"Vaccination;Quarantine"`

## Output

- `{log_dir}/screening.jsonl` - All screening decisions
- `{log_dir}/extractions.jsonl` - All extraction attempts
- `{log_dir}/extracted_models.csv` - Final results (one row per article, multi-select fields semicolon-separated)
