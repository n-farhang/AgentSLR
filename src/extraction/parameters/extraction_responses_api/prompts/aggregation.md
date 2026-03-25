# Aggregation task
For your next task, you will be provided with a list of parameters already extracted from an epidemiological study. Your task is to provide _aggregations_ of these parameter values when suitable.

## Aggregation context
Some epidemiological papers have a huge level of parameter disaggregation (e.g. age, sex, location) and so we have established different rules to ease our meta-review process. For non-location-related disaggregations, please remember the **rule of three**. If there are three or more disaggregations for a parameter, e.g. Rt values for three or more age groups, extract these as a **range** and specify that disaggregated data is available and what the parameter is disaggregated by.

Each pathogen has different rules on location, which we state here:
- marburg; ebola; MERS: Location is included within the rule of three.
- lassa; SARS; zika; nipah: Please _do not aggregate_ values if the disaggregation is by location as much as possible and do not apply the rule of three for geographic regions down to admin level 2 (sub-regions) of a country. However, please respect the rule of three for estimates by neighborhood for example.

If the provided parameters do not contain adequate population information to perform an aggregation, then do not return any aggregated values.

If you decide that an aggregation is necessary, use the provided tool to submit aggregated values according to the tool's schema. Provide the `lower_bound` and `upper_bound` of the parameter values, and list the types of population disaggregation (like "age", "sex", etc.) in the `disaggregated_by` field. Fill the `aggregated_ids` list with all of the `id`s from the parameters you aggregated.
