# Outbreak Extraction

Extract **concluded outbreaks** with defined case counts from the article. Call `extract_outbreak_data` once for each distinct outbreak (different location, time, or both).

## Important Notes

We are extracting everything as presented in the paper, even if you think it's an error by the author(s).

Extract data EXACTLY as stated in the paper. Do NOT perform calculations, convert units, or infer missing values.

DO NOT use commas in any field. If you need to separate items within a field, please use a semi-colon.

## Tool Calling Rules

- Call `extract_outbreak_data` **once per distinct outbreak**
- Outbreaks are distinct if they differ by location, time, or both
- After extracting all outbreaks, stop calling the tool (no completion call needed)

## Schema Requirements

Only three fields are **required**:
- `outbreak_is_currently_ongoing`: true or false
- `outbreak_country`: Must be valid WHO country name
- `asymptomatic_transmission_described`: true or false

All other fields: Use `null` when not stated in the paper.

## Extraction Rules

- Only select values that appear in the allowed lists for categorical fields
- Extract dates as separate components (day, month, year)
- Do NOT calculate `outbreak_duration_months` - only extract if explicitly stated
- If you receive a validation error message, correct the tool call and try again

## Field-Specific Guidance

**Location**:
- `outbreak_country`: MUST match WHO standard names exactly (e.g., "United States of America" not "USA", "Viet Nam" not "Vietnam")
- `outbreak_location`: Extract as written; use semicolons not commas (e.g., "Lagos; Abuja")

**Case Counts**: Extract all categories as reported
- `cases_confirmed`: Laboratory-confirmed cases
- `cases_probable`: Probable cases (clinical diagnosis)
- `cases_suspected`: Suspected cases under investigation
- `cases_unspecified`: Cases without clear classification
- `cases_asymptomatic`: Asymptomatic cases identified
- `cases_severe`: Severe cases OR hospitalizations (note if hospitalizations in `notes`)
- `deaths`: Reported deaths

**Mode of Detection**: Select ONE
- **"Molecular (PCR etc)"**: Laboratory confirmation (PCR, ELISA, culture, etc.)
- **"Symptoms"**: Clinical/syndromic diagnosis only
- **"Confirmed + Suspected"**: Both lab-confirmed and clinical cases
- **"Unspecified"**: Not clearly stated

**Sex Disaggregation**: When provided, extract:
- `male_cases` / `female_cases`: Counts
- `prop_male_cases` / `prop_female_cases`: Proportion/percentage as reported
- `type_cases_sex_disagg`: Which case type is disaggregated (Confirmed/Suspected/Other/Unspecified)

**Pre-Outbreak Baseline**:
- **"Disease-free baseline"**: No previous cases
- **"Endemic equilibrium"**: Disease was endemic
- **"Probable"**: Suggested but not definitive
- **"Unspecified"**: Not discussed

**Dates**: Provide as separate components (day, month, year). Partial dates are acceptable (e.g., only month and year).

**Duration**: ONLY extract if paper explicitly states duration. Do NOT calculate from dates.

**Notes**: Use this field for important context, data quality issues, or special circumstances.

## Pathogen-Specific Rules

- **Zika, RVF**: Only extract outbreaks with ≥10 cases
- **Marburg, Lassa, Nipah**: Extract all outbreaks
- **OROV**: Include even single case reports