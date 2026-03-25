# src/extraction/parameters/extraction_responses_api/tools/seroprevalence/extractor.py
from ..extractor import (
    ParameterExtractionResult, ParameterExtractor
)
from typing import Optional


class SeroprevalenceExtractor(ParameterExtractor):
    PARAMETER_TYPES = [
        "IgG",
        "IgM",
        "PRNT",
        "HAI",
        "IFA",
        "Unspecified"
    ]

    @property
    def TOOL_CALL(self) -> dict:
        return {
            "type": "function",
            "name": "extract_seroprevalence_value",
            "description": (
                "Extract seroprevalence parameter values from the provided article text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": (
                            "The seroprevalence value as a proportion between 0.0 and 1.0."
                        ),
                    },
                    "parameter_type": {
                        "type": "string",
                        "description": (
                            "The type of seroprevalence parameter (assay type). "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(self.PARAMETER_TYPES)}."
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
                },
                "required": ["value", "parameter_type"],
            },
        }

    def extract_value(
        self,
        parameter: str,
        value: float,
        parameter_type: str,
        numerator: Optional[int],
        denominator: Optional[int],
    ) -> ParameterExtractionResult:
        errors = []

        if parameter_type not in self.PARAMETER_TYPES:
            errors.append(
                f"Invalid seroprevalence type '{parameter_type}'. "
                f"Allowed types are: {self.PARAMETER_TYPES}"
            )

        if value < 0.0 or value > 1.0:
            errors.append(
                f"Invalid seroprevalence value '{value}'. "
                "Value must be between 0.0 and 1.0."
            )

        return self.return_result(
            parameter=parameter,
            errors=errors,
            content={
                "value": value,
                "parameter_type": parameter_type,
                "numerator": numerator,
                "denominator": denominator,
            }
        )
