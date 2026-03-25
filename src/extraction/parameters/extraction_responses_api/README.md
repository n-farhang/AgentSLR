# Parameter Extraction

Following the full-text, we use an LLM with tool calling to extract parameter estimates.

## Parameter classes

We organise our parameter extraction logic around _parameter classes_. PERG defines a group-level mapping [in their database post-processing](https://github.com/mrc-ide/priority-pathogens/blob/c334ca32b95d1a0cbd64ef3ec011488452b8524e/src/db_cleaning/template_cleaning_config.R#L44-L57), which then fill the `parameter_class` field in each `{parameter}_parameters.csv` [obtained from PERG](https://github.com/mrc-ide/epireview/tree/main/inst/extdata).

There are 12 parameter classes, plus a 13th "other" class. We map each parameter class to a variable name and define a custom tool call for extraction:

| **PERG parameter class** | **Our parameter class** |
|---|---|
| Attack rate | [`attack_rate`](./tools/attack_rate) |
| Doubling time | ⚠️ Not implemented |
| Growth rate | [`growth_rate`](./tools/growth_rate) |
| Human delay | [`human_delay`](./tools/human_delay) |
| Mosquito | ⚠️ Not implemented |
| Mutations | [`mutation_rate`](./tools/mutation_rate) |
| Other transmission parameters | ⚠️ Not implemented |
| Overdispersion | ⚠️ Not implemented |
| Relative contribution | [`relative_contribution`](./tools/relative_contribution) |
| Reproduction number | [`reproduction_number`](./tools/reproduction_number) |
| Risk factors | ⚠️ Not implemented |
| Seroprevalence | [`seroprevalence`](./tools/seroprevalence) |
| Severity | [`severity`](./tools/severity) |

Each of these parameter classes has a number of different valid `parameter_types` that can be extracted, as well as (potentially custom) logic for handling aggregation at the population level, documenting study design, etc. To handle the extraction process in a modular fashion, each parameter class has a dedicated module within the `tools/` subdirectory. Each module is structured like so:
```
tools/{parameter_type}/
├── extractor.py
├── system_prompt.md
└── tool_call.py
```

Within `extractor.py`, we define a `{ParameterType}Extractor` class that inherits from the base `ParameterExtractor` class defined in `tools/extractor.py`.