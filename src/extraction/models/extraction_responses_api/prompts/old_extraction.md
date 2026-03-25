# Model Extraction

Extract **dynamic transmission models** (e.g., compartmental, branching process, agent/individual-based) described in the article. Do **not** extract regression-only analyses, purely statistical forecasting, or descriptive summaries that are not transmission models.

## Tool Calling Rules

- Call `extract_model_data` once **per distinct model identified** in the paper.
- Use `model_index` as a 1-indexed counter (1, 2, 3, ...).
- After you have called `extract_model_data` for all models, call `extraction_complete` **exactly once**.

## Schema Requirements

All fields must be provided in every `extract_model_data` call. Use:
- `null` for optional fields when not stated.
- `["Unspecified"]` when the article does not state any items for an array field.

Important:
- `assumptions` must be a **non-empty** array. If the paper does not state assumptions explicitly, use `["Unspecified"]`.
- `interventions_type` must be a **non-empty** array. If no interventions are modeled, use `["Unspecified"]`.
- Do not use empty arrays.

## Extraction Rules

- Only select enum values that appear in the allowed lists.
- Do not invent model characteristics that are not stated in the article.
- If you receive a validation error message, correct the tool call and try again.
