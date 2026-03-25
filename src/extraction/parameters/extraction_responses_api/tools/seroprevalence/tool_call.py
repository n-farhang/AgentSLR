# src/extraction/parameters/extraction_responses_api/tools/seroprevalence/tool_call.py
from ..extractor import ParameterExtractor
from .extractor import SeroprevalenceExtractor

SEROPREVALENCE_TOOL_CALL = {
    "type": "function",
    "name": "extract_seroprevalence_parameter",
    "description": "Extract seroprevalence parameters from the provided article text.",
    "parameters": {
        "properties": {
            "parameter_type": {
                "type": "string",
                "description": (
                    "The type of seroprevalence parameter. "
                    "Can take ONLY one of the following values: "
                    f"{', '.join(SeroprevalenceExtractor.PARAMETER_TYPES)}."
                ),
            },
            "value": {
                "type": "number",
                "description": (
                    "The seroprevalence value as a proportion between 0.0 and 1.0."
                ),
            },
            "numerator": {
                "type": ["integer", "null"],
                "description": (
                    "The numerator used to calculate the seroprevalence value. "
                    "If not provided, set to null."
                ),
            },
            "denominator": {
                "type": ["integer", "null"],
                "description": (
                    "The denominator used to calculate the seroprevalence value. "
                    "If not provided, set to null."
                ),
            },
            "population_sex": {
                "type": ["string", "null"],
                "description": (
                    "The sex composition of your study population. If you have 99 men "
                    "and 1 woman you would still put both in this option. "
                    "If provided, can take ONLY one of the following values: "
                    f"{', '.join(ParameterExtractor.POPULATION_SEXES)}."
                ),
            },
            "population_sample_size": {
                "type": ["integer", "null"],
                "description": (
                    "The number of participants/samples tested. "
                    "If not provided, set to null."
                ),
            },
            "population_sample_type": {
                "type": ["string", "null"],
                "description": (
                    "How was the study conducted? "
                    "If provided, can take ONLY one of the following values: "
                    f"{', '.join(ParameterExtractor.POPULATION_SAMPLE_TYPES)}."
                ),
            },
            "population_group": {
                "type": ["string", "null"],
                "description": (
                    "The demographic, e.g. who was tested? "
                    "If provided, can take ONLY one of the following values: "
                    f"{', '.join(ParameterExtractor.POPULATION_GROUPS)}."
                ),
            },
            "population_age_min": {
                "type": ["integer", "null"],
                "description": (
                    "The minimum age of the study population. "
                    "If your sample is people over 18 you would set "
                    "population_age_min = 18 and set population_age_max to null. "
                    "If not provided, set to null."
                ),
            },
            "population_age_max": {
                "type": ["integer", "null"],
                "description": (
                    "The maximum age of the study population. "
                    "If not provided, set to null."
                ),
            },
            "population_country": {
                "type": ["string", "null"],
                "description": (
                    "The country where the study was conducted. "
                    "If not provided, set to null."
                ),
            },
            "population_location": {
                "type": ["string", "null"],
                "description": (
                    "The specific location reported (e.g., city, region, hospital). "
                    "If not provided, set to null."
                ),
            },
        },
        "required": ["parameter_type", "value"],
    },
}
