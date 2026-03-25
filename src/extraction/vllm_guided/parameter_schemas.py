# src/extraction/vllm_guided/parameter_schemas.py
"""
JSON Schemas for vLLM guided decoding - Parameter extraction.

These schemas are designed to work with the Outlines library and enforce
strict output format during model inference for parameter extraction.
"""

import json

# Import enum lists from the parameter extractor
from ..parameters.extraction_responses_api.tools.extractor import ParameterExtractor

# Get enum values from base class
POPULATION_SEXES = ParameterExtractor.POPULATION_SEXES
POPULATION_SAMPLE_TYPES = ParameterExtractor.POPULATION_SAMPLE_TYPES
POPULATION_GROUPS = ParameterExtractor.POPULATION_GROUPS
VALUE_TYPES = ParameterExtractor.VALUE_TYPES
STATISTICAL_APPROACHES = ParameterExtractor.STATISTICAL_APPROACHES
SINGLE_TYPE_UNCERTAINTIES = ParameterExtractor.SINGLE_TYPE_UNCERTAINTIES
PAIRED_UNCERTAINTIES = ParameterExtractor.PAIRED_UNCERTAINTIES
DISTRIBUTION_TYPES = ParameterExtractor.DISTRIBUTION_TYPES


# ============================================================================
# SCREENING SCHEMA
# ============================================================================

SCREENING_GUIDED_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "contains_parameter": {
            "type": "boolean"
        },
        "annotations": {
            "type": "string"  # Use empty string for null
        }
    },
    "required": ["contains_parameter", "annotations"],
    "additionalProperties": False
}


# ============================================================================
# UNCERTAINTY SCHEMA
# ============================================================================

UNCERTAINTY_GUIDED_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "value_type": {
            "type": "string",
            "enum": VALUE_TYPES
        },
        "statistical_approach": {
            "type": "string",
            "enum": STATISTICAL_APPROACHES
        },
        "single_type_uncertainty": {
            "type": "string",
            "enum": SINGLE_TYPE_UNCERTAINTIES + ["null"]
        },
        "single_type_uncertainty_value": {
            "type": "number"  # Use 0 for null
        },
        "paired_uncertainty": {
            "type": "string",
            "enum": PAIRED_UNCERTAINTIES + ["null"]
        },
        "paired_uncertainty_lower_bound": {
            "type": "number"  # Use 0 for null
        },
        "paired_uncertainty_upper_bound": {
            "type": "number"  # Use 0 for null
        },
        "distribution_type": {
            "type": "string",
            "enum": DISTRIBUTION_TYPES + ["null"]
        }
    },
    "required": [
        "value_type", "statistical_approach", "single_type_uncertainty",
        "single_type_uncertainty_value", "paired_uncertainty",
        "paired_uncertainty_lower_bound", "paired_uncertainty_upper_bound",
        "distribution_type"
    ],
    "additionalProperties": False
}


# ============================================================================
# POPULATION SCHEMA
# ============================================================================

POPULATION_GUIDED_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "population_sex": {
            "type": "string",
            "enum": POPULATION_SEXES
        },
        "population_sample_type": {
            "type": "string",
            "enum": POPULATION_SAMPLE_TYPES
        },
        "population_group": {
            "type": "string",
            "enum": POPULATION_GROUPS
        },
        "population_sample_size": {
            "type": "integer"  # Use 0 for null
        },
        "population_age_min": {
            "type": "integer"  # Use 0 for null
        },
        "population_age_max": {
            "type": "integer"  # Use 0 for null
        },
        "population_country": {
            "type": "string"  # Use empty string for null
        },
        "population_location": {
            "type": "string"  # Use empty string for null
        }
    },
    "required": [
        "population_sex", "population_sample_type", "population_group",
        "population_sample_size", "population_age_min", "population_age_max",
        "population_country", "population_location"
    ],
    "additionalProperties": False
}


# ============================================================================
# AGGREGATION SCHEMA
# ============================================================================

AGGREGATION_GUIDED_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "lower_bound": {
            "type": "number"
        },
        "upper_bound": {
            "type": "number"
        },
        "disaggregated_by": {
            "type": "array",
            "items": {"type": "string"}
        },
        "aggregated_ids": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["lower_bound", "upper_bound", "disaggregated_by", "aggregated_ids"],
    "additionalProperties": False
}


# ============================================================================
# PARAMETER-SPECIFIC VALUE EXTRACTION SCHEMAS
# ============================================================================

# Import parameter-specific extractors to get their enums
from ..parameters.extraction_responses_api.tools.reproduction_number.extractor import ReproductionNumberExtractor
from ..parameters.extraction_responses_api.tools.attack_rate.extractor import AttackRateExtractor
from ..parameters.extraction_responses_api.tools.growth_rate.extractor import GrowthRateExtractor
from ..parameters.extraction_responses_api.tools.human_delay.extractor import HumanDelayExtractor
from ..parameters.extraction_responses_api.tools.mutation_rate.extractor import MutationRateExtractor
from ..parameters.extraction_responses_api.tools.relative_contribution.extractor import RelativeContributionExtractor
from ..parameters.extraction_responses_api.tools.seroprevalence.extractor import SeroprevalenceExtractor
from ..parameters.extraction_responses_api.tools.severity.extractor import SeverityExtractor


# Reproduction Number
REPRODUCTION_NUMBER_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["extract", "done"]
        },
        "data": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "type": {
                    "type": "string",
                    "enum": ReproductionNumberExtractor.TYPES
                },
                "transmission": {
                    "type": "string",
                    "enum": ReproductionNumberExtractor.TRANSMISSIONS
                },
                "method": {
                    "type": "string",
                    "enum": ReproductionNumberExtractor.METHODS
                }
            },
            "required": ["value", "type", "transmission", "method"],
            "additionalProperties": False
        }
    },
    "required": ["action"],
    "additionalProperties": False
}

# Attack Rate
ATTACK_RATE_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["extract", "done"]
        },
        "data": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "unit": {
                    "type": "string",
                    "enum": AttackRateExtractor.UNITS
                },
                "rate_denominator": {
                    "type": "integer"  # Use 0 for null
                }
            },
            "required": ["value", "unit", "rate_denominator"],
            "additionalProperties": False
        }
    },
    "required": ["action"],
    "additionalProperties": False
}

# Growth Rate
GROWTH_RATE_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["extract", "done"]
        },
        "data": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "unit": {
                    "type": "string",
                    "enum": GrowthRateExtractor.UNITS
                }
            },
            "required": ["value", "unit"],
            "additionalProperties": False
        }
    },
    "required": ["action"],
    "additionalProperties": False
}

# Human Delay
HUMAN_DELAY_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["extract", "done"]
        },
        "data": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "delay_type": {
                    "type": "string",
                    "enum": HumanDelayExtractor.DELAY_TYPES
                },
                "unit": {
                    "type": "string",
                    "enum": HumanDelayExtractor.UNITS
                },
                "delay_type_note": {
                    "type": "string"  # Use empty string for null
                }
            },
            "required": ["value", "delay_type", "unit", "delay_type_note"],
            "additionalProperties": False
        }
    },
    "required": ["action"],
    "additionalProperties": False
}

# Mutation Rate
MUTATION_RATE_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["extract", "done"]
        },
        "data": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "parameter_type": {
                    "type": "string",
                    "enum": MutationRateExtractor.PARAMETER_TYPES
                },
                "unit": {
                    "type": "string",
                    "enum": MutationRateExtractor.UNITS
                },
                "genome_site": {
                    "type": "string"
                }
            },
            "required": ["value", "parameter_type", "unit", "genome_site"],
            "additionalProperties": False
        }
    },
    "required": ["action"],
    "additionalProperties": False
}

# Relative Contribution
RELATIVE_CONTRIBUTION_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["extract", "done"]
        },
        "data": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "type": {
                    "type": "string",
                    "enum": RelativeContributionExtractor.TYPES
                }
            },
            "required": ["value", "type"],
            "additionalProperties": False
        }
    },
    "required": ["action"],
    "additionalProperties": False
}

# Seroprevalence
SEROPREVALENCE_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["extract", "done"]
        },
        "data": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "parameter_type": {
                    "type": "string",
                    "enum": SeroprevalenceExtractor.PARAMETER_TYPES
                },
                "numerator": {
                    "type": "integer"  # Use 0 for null
                },
                "denominator": {
                    "type": "integer"  # Use 0 for null
                }
            },
            "required": ["value", "parameter_type", "numerator", "denominator"],
            "additionalProperties": False
        }
    },
    "required": ["action"],
    "additionalProperties": False
}

# Severity
SEVERITY_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["extract", "done"]
        },
        "data": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "numerator": {
                    "type": "integer"  # Use 0 for null
                },
                "denominator": {
                    "type": "integer"  # Use 0 for null
                },
                "parameter_type": {
                    "type": "string",
                    "enum": SeverityExtractor.PARAMETER_TYPES
                },
                "method": {
                    "type": "string",
                    "enum": SeverityExtractor.METHODS + ["null"]
                },
                "value_type": {
                    "type": "string",
                    "enum": SeverityExtractor.VALUE_TYPES
                },
                "statistical_approach": {
                    "type": "string",
                    "enum": SeverityExtractor.STATISTICAL_APPROACHES
                }
            },
            "required": [
                "value",
                "numerator",
                "denominator",
                "parameter_type",
                "method",
                "value_type",
                "statistical_approach",
            ],
            "additionalProperties": False
        }
    },
    "required": ["action"],
    "additionalProperties": False
}


# Mapping from parameter class name to schema
PARAMETER_VALUE_SCHEMAS = {
    "reproduction_number": REPRODUCTION_NUMBER_VALUE_SCHEMA,
    "attack_rate": ATTACK_RATE_VALUE_SCHEMA,
    "growth_rate": GROWTH_RATE_VALUE_SCHEMA,
    "human_delay": HUMAN_DELAY_VALUE_SCHEMA,
    "mutation_rate": MUTATION_RATE_VALUE_SCHEMA,
    "relative_contribution": RELATIVE_CONTRIBUTION_VALUE_SCHEMA,
    "seroprevalence": SEROPREVALENCE_VALUE_SCHEMA,
    "severity": SEVERITY_VALUE_SCHEMA,
}


def get_schema_json(schema: dict) -> str:
    """Convert schema dict to JSON string (for logging/debugging).
    
    Note: vLLM v0.12+ uses structured_outputs with dict schemas directly.
    Use extra_body={"structured_outputs": {"json": schema}} instead of
    the deprecated guided_json parameter.
    """
    return json.dumps(schema)
