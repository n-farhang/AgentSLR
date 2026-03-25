# src/extraction/vllm_guided/schemas.py
"""
JSON Schemas for vLLM guided decoding.

These schemas are designed to work with the Outlines library and enforce
strict output format during model inference. They mirror the tool call
schemas but use formats compatible with grammar-constrained decoding.

Key differences from tool call schemas:
- No ["type", "null"] - use "null" as enum value for nullable strings
- Native boolean/integer types where JSON schema supports them
- Use 0 for "not available" integers (converted to None post-processing)
"""

import json

# Import enum lists from original tools modules
from ..models.extraction.tools import (
    MODEL_TYPES,
    COMPARTMENTAL_TYPES,
    STOCH_DETER,
    TRANSMISSION_ROUTES,
    ASSUMPTIONS,
    INTERVENTIONS,
    CODING_LANGUAGES,
    DATA_AVAILABILITY,
)

from ..outbreaks.extraction.tools import (
    MONTHS,
    COUNTRIES,
    OUTBREAK_SOURCES,
    MODE_OF_DETECTION,
    PRE_OUTBREAK_STATUS,
    SEX_DISAGG_TYPES,
)


# ============================================================================
# MODEL EXTRACTION SCHEMAS
# ============================================================================

MODEL_GUIDED_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["extract_model", "done"]
        },
        "model_data": {
            "type": "object",
            "properties": {
                # Required string enums (non-nullable)
                "model_type": {
                    "type": "string",
                    "enum": MODEL_TYPES
                },
                "compartmental_type": {
                    "type": "string",
                    "enum": COMPARTMENTAL_TYPES
                },
                # Nullable string enum - use "null" in enum
                "stoch_deter": {
                    "type": "string",
                    "enum": STOCH_DETER + ["null"]
                },
                # Required array of enum strings
                "transmission_route": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": TRANSMISSION_ROUTES
                    },
                    "minItems": 1
                },
                # Native booleans
                "uncertainty_was_considered": {
                    "type": "boolean"
                },
                "spatial_model": {
                    "type": "boolean"
                },
                "spillover_included": {
                    "type": "boolean"
                },
                # Required array of enum strings
                "assumptions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ASSUMPTIONS
                    },
                    "minItems": 1
                },
                # Required boolean
                "theoretical_model": {
                    "type": "boolean"
                },
                # Required array of enum strings
                "interventions_type": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": INTERVENTIONS
                    },
                    "minItems": 1
                },
                # Required boolean
                "code_available": {
                    "type": "boolean"
                },
                # Nullable string enums
                "coding_language": {
                    "type": "string",
                    "enum": CODING_LANGUAGES + ["null"]
                },
                "is_data_used_available": {
                    "type": "string",
                    "enum": DATA_AVAILABILITY + ["null"]
                },
                # Boolean
                "readme_included": {
                    "type": "boolean"
                },
                # Free-form string for notes (empty string if none)
                "notes": {
                    "type": "string"
                }
            },
            "required": [
                "model_type", "compartmental_type", "stoch_deter", "transmission_route",
                "uncertainty_was_considered", "spatial_model", "spillover_included",
                "assumptions", "theoretical_model", "interventions_type", "code_available",
                "coding_language", "is_data_used_available", "readme_included", "notes"
            ],
            "additionalProperties": False
        }
    },
    "required": ["action"]
}


MODEL_PROVENANCE_GUIDED_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "model_type_excerpt": {"type": "string"},
        "compartmental_type_excerpt": {"type": "string"},
        "stoch_deter_excerpt": {"type": "string"},
        "transmission_route_excerpts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value": {"type": "string", "enum": TRANSMISSION_ROUTES},
                    "excerpt": {"type": "string"}
                },
                "required": ["value", "excerpt"],
                "additionalProperties": False
            }
        },
        "assumptions_excerpts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value": {"type": "string", "enum": ASSUMPTIONS},
                    "excerpt": {"type": "string"}
                },
                "required": ["value", "excerpt"],
                "additionalProperties": False
            }
        },
        "interventions_type_excerpts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value": {"type": "string", "enum": INTERVENTIONS},
                    "excerpt": {"type": "string"}
                },
                "required": ["value", "excerpt"],
                "additionalProperties": False
            }
        },
        "coding_language_excerpt": {"type": "string"},
        "data_availability_excerpt": {"type": "string"}
    },
    "required": [
        "model_type_excerpt", "compartmental_type_excerpt", "stoch_deter_excerpt",
        "transmission_route_excerpts", "assumptions_excerpts", "interventions_type_excerpts",
        "coding_language_excerpt", "data_availability_excerpt"
    ],
    "additionalProperties": False
}


# ============================================================================
# OUTBREAK EXTRACTION SCHEMAS
# ============================================================================

OUTBREAK_GUIDED_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["extract_outbreak", "done"]
        },
        "outbreak_data": {
            "type": "object",
            "properties": {
                # Date fields - integers (use 0 for null)
                "outbreak_start_day": {"type": "integer"},
                "outbreak_start_month": {
                    "type": "string",
                    "enum": MONTHS + ["null"]
                },
                "outbreak_start_year": {"type": "integer"},
                "outbreak_end_day": {"type": "integer"},
                "outbreak_end_month": {
                    "type": "string",
                    "enum": MONTHS + ["null"]
                },
                "outbreak_end_year": {"type": "integer"},
                "outbreak_duration_months": {"type": "number"},
                # Boolean
                "outbreak_is_currently_ongoing": {"type": "boolean"},
                # Location
                "outbreak_country": {
                    "type": "string",
                    "enum": COUNTRIES
                },
                "outbreak_location": {"type": "string"},
                "outbreak_location_type": {"type": "string"},
                # Categorical fields
                "outbreak_source": {
                    "type": "string",
                    "enum": OUTBREAK_SOURCES + ["null"]
                },
                "mode_of_detection": {
                    "type": "string",
                    "enum": MODE_OF_DETECTION + ["null"]
                },
                "method_of_case_definition": {"type": "string"},
                "pre_outbreak": {
                    "type": "string",
                    "enum": PRE_OUTBREAK_STATUS + ["null"]
                },
                # Case counts - integers (use 0 for null)
                "cases_confirmed": {"type": "integer"},
                "cases_probable": {"type": "integer"},
                "cases_suspected": {"type": "integer"},
                "cases_unspecified": {"type": "integer"},
                "cases_asymptomatic": {"type": "integer"},
                "cases_severe": {"type": "integer"},
                "deaths": {"type": "integer"},
                # Boolean
                "asymptomatic_transmission_described": {"type": "boolean"},
                # Population
                "population_size_geographical_area": {"type": "integer"},
                # Sex disaggregation
                "type_cases_sex_disagg": {
                    "type": "string",
                    "enum": SEX_DISAGG_TYPES + ["null"]
                },
                "male_cases": {"type": "integer"},
                "prop_male_cases": {"type": "number"},
                "female_cases": {"type": "integer"},
                "prop_female_cases": {"type": "number"},
                # Notes
                "notes": {"type": "string"}
            },
            "required": [
                "outbreak_start_day", "outbreak_start_month", "outbreak_start_year",
                "outbreak_end_day", "outbreak_end_month", "outbreak_end_year",
                "outbreak_duration_months", "outbreak_is_currently_ongoing",
                "outbreak_country", "outbreak_location", "outbreak_location_type",
                "outbreak_source", "mode_of_detection", "method_of_case_definition",
                "pre_outbreak", "cases_confirmed", "cases_probable", "cases_suspected",
                "cases_unspecified", "cases_asymptomatic", "cases_severe", "deaths",
                "asymptomatic_transmission_described", "population_size_geographical_area",
                "type_cases_sex_disagg", "male_cases", "prop_male_cases",
                "female_cases", "prop_female_cases", "notes"
            ],
            "additionalProperties": False
        }
    },
    "required": ["action"]
}


OUTBREAK_PROVENANCE_GUIDED_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "outbreak_country_excerpt": {"type": "string"},
        "outbreak_location_excerpt": {"type": "string"},
        "outbreak_start_excerpt": {"type": "string"},
        "outbreak_end_excerpt": {"type": "string"},
        "outbreak_duration_excerpt": {"type": "string"},
        "outbreak_source_excerpt": {"type": "string"},
        "mode_of_detection_excerpt": {"type": "string"},
        "method_of_case_definition_excerpt": {"type": "string"},
        "pre_outbreak_excerpt": {"type": "string"},
        "cases_confirmed_excerpt": {"type": "string"},
        "cases_probable_excerpt": {"type": "string"},
        "cases_suspected_excerpt": {"type": "string"},
        "cases_unspecified_excerpt": {"type": "string"},
        "cases_asymptomatic_excerpt": {"type": "string"},
        "cases_severe_excerpt": {"type": "string"},
        "deaths_excerpt": {"type": "string"},
        "asymptomatic_transmission_excerpt": {"type": "string"},
        "population_size_excerpt": {"type": "string"},
        "sex_disaggregation_excerpt": {"type": "string"}
    },
    "required": [
        "outbreak_country_excerpt", "outbreak_location_excerpt",
        "outbreak_start_excerpt", "outbreak_end_excerpt",
        "outbreak_duration_excerpt", "outbreak_source_excerpt",
        "mode_of_detection_excerpt", "method_of_case_definition_excerpt",
        "pre_outbreak_excerpt", "cases_confirmed_excerpt",
        "cases_probable_excerpt", "cases_suspected_excerpt",
        "cases_unspecified_excerpt", "cases_asymptomatic_excerpt",
        "cases_severe_excerpt", "deaths_excerpt",
        "asymptomatic_transmission_excerpt", "population_size_excerpt",
        "sex_disaggregation_excerpt"
    ],
    "additionalProperties": False
}


# ============================================================================
# UTILITIES
# ============================================================================

def get_schema_json(schema: dict) -> str:
    """Convert schema dict to JSON string (for logging/debugging).
    
    Note: vLLM v0.12+ uses structured_outputs with dict schemas directly.
    Use extra_body={"structured_outputs": {"json": schema}} instead of
    the deprecated guided_json parameter.
    """
    return json.dumps(schema)
