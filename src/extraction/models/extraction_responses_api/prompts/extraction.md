# Model Extraction
Extract **ALL dynamic transmission models** described in the article that were actually used or implemented.

Do **not** extract:
- Models only mentioned as possible alternatives without implementation
- Regression-only analyses  
- Purely statistical forecasting

## Tool Calling
- Call `extract_model_data` **once per model** identified in the article
- After extracting all model/s, stop calling the tool (no completion call needed)

## Schema Requirements
- `transmission_route`, `assumptions`, `interventions_type` are **arrays** (multiple-select)
- All other fields are **single values** (single-select)
- Use `null` for optional single-select fields when not stated
- Use `["Unspecified"]` for required arrays when not stated