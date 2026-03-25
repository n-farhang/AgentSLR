# Provenance Extraction

For each outbreak field value that was extracted, provide the specific excerpt from the article that supports that extraction. This helps validate and audit the extraction by grounding each value to its source in the text.

## Task

You have already extracted outbreak data from this article. Now, find and provide the exact quotes or passages that justify each extracted value for the given outbreak.

## Requirements

- Provide excerpts for ALL non-null values that were extracted
- Excerpts should be direct quotes from the article
- Each excerpt should clearly support the corresponding extracted value
- If a value appears in multiple places, choose the most clear and complete excerpt
- For null/unspecified values, provide null as the excerpt
- Numeric values should have excerpts showing the source of that number

## Fields to Provide Excerpts For

Provide excerpts for these key fields when they have non-null values:
- outbreak_country: Quote showing the country
- outbreak_location: Quote showing the specific location
- outbreak_start_year/month/day: Quote showing when the outbreak started
- outbreak_end_year/month/day: Quote showing when the outbreak ended
- outbreak_duration_months: Quote explicitly stating duration (do not calculate)
- outbreak_source: Quote describing the source of infection
- mode_of_detection: Quote describing how cases were detected
- cases_confirmed: Quote with the confirmed case count
- cases_probable: Quote with the probable case count
- cases_suspected: Quote with the suspected case count
- cases_unspecified: Quote with the unspecified case count
- deaths: Quote with the death count
- population_size_geographical_area: Quote with the population size

## Examples

**Good excerpts:**
- outbreak_country = "Nigeria" → excerpt: "The outbreak occurred in the Edo State of Nigeria"
- cases_confirmed = 42 → excerpt: "A total of 42 laboratory-confirmed cases were reported"
- outbreak_start_year = 2018 → excerpt: "The outbreak began in January 2018"
- deaths = 15 → excerpt: "Of these cases, 15 resulted in death (CFR 35.7%)"

**Bad excerpts:**
- Too vague: "see Table 1"
- Paraphrased: "About forty cases were found" (when exact number was extracted)
- Missing: No excerpt provided for an extracted value
