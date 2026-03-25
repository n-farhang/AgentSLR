# Verification Task

You are verifying extracted model data against the original article. For each model extraction provided, confirm whether each field value is supported by the article text.

## Instructions

1. Review the extracted data for each model
2. Check each field against the article content
3. Call `verify_extraction` for each model with:
   - `is_valid`: true if all required fields are correct
   - `field_verifications`: boolean for each field indicating correctness
   - `corrections`: provide corrected values for any incorrect fields (null if all correct)
   - `reasoning`: brief explanation

## Verification Criteria

- **Correct**: Value is explicitly supported by article text
- **Correct (null)**: Field appropriately null when info not in article
- **Incorrect**: Value contradicts article or info exists but was missed

Be strict—only mark as correct if the article explicitly supports the extracted value.