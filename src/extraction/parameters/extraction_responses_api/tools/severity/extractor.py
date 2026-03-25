# src/extraction/parameters/extraction_responses_api/tools/severity/extractor.py
from ..extractor import (
    ParameterExtractionResult, ParameterExtractor
)
from typing import Optional


class SeverityExtractor(ParameterExtractor):
    PARAMETER_TYPES = ["CFR", "IFR", "proportion_of_symptomatic_cases", "proportion_of_asymptomatic_cases"]
    METHODS = ["naive", "adjusted", "unknown"]
    VALUE_TYPES = [
        "mean",
        "median",
        "mode",
        "central",
        "maximum_likelihood",
        "shape",
        "other",
        "unspecified"
    ]
    STATISTICAL_APPROACHES = [
        "observed_sample_statistic",
        "estimated_model_parameter",
        "case_study",
        "unspecified"
    ]

    @property
    def TOOL_CALL(self) -> dict:
        return {
            "type": "function",
            "name": "extract_severity_value",
            "description": (
                "Extract severity parameter values from the provided article text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": (
                            "The value of the severity parameter as a proportion "
                            "between 0.0 and 1.0."
                        ),
                    },
                    "numerator": {
                        "type": ["integer", "null"],
                        "description": (
                            "The numerator of the CFR or IFR parameter, if provided."
                        ),
                    },
                    "denominator": {
                        "type": ["integer", "null"],
                        "description": (
                            "The denominator of the CFR or IFR parameter, if provided."
                        ),
                    },
                    "parameter_type": {
                        "type": "string",
                        "description": (
                            "The type of severity parameter reported. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(self.PARAMETER_TYPES)}."
                        ),
                    },
                    "method": {
                        "type": ["string", "null"],
                        "description": (
                            "The method used to calculate the CFR or IFR. If not null, "
                            "can take ONLY one of the following values: "
                            f"{self.METHODS}."
                        ),
                    },
                    "value_type": {
                        "type": "string",
                        "description": (
                            "The parameter value type. See the longer description in "
                            "the system prompt for more information. Can take ONLY one "
                            f"of the following values: {self.VALUE_TYPES}."
                        )
                    },
                    "statistical_approach": {
                        "type": "string",
                        "description": (
                            "The statistical approach used to estimate the parameter. "
                            "Can take ONLY one of the following values: "
                            f"{self.STATISTICAL_APPROACHES}."
                        )
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
            },
        }

    def extract_value(
        self,
        parameter: str,
        value: float,
        numerator: Optional[int],
        denominator: Optional[int],
        parameter_type: str,
        method: Optional[str],
        value_type: str,
        statistical_approach: str,
    ) -> ParameterExtractionResult:
        errors = []
        if parameter_type not in self.PARAMETER_TYPES:
            errors.append(
                f"Invalid severity parameter_type '{parameter_type}'. "
                f"Allowed parameter types are: {self.PARAMETER_TYPES}"
            )

        if method not in self.METHODS:
            errors.append(
                f"Invalid severity method '{method}'. "
                f"Allowed methods are: {self.METHODS}"
            )

        if value_type not in self.VALUE_TYPES:
            errors.append(
                f"Invalid value_type '{value_type}'. "
                f"Allowed value types are: {self.VALUE_TYPES}"
            )
        if statistical_approach not in self.STATISTICAL_APPROACHES:
            errors.append(
                f"Invalid statistical_approach '{statistical_approach}'. "
                f"Allowed statistical approaches are: {self.STATISTICAL_APPROACHES}"
            )

        return self.return_result(
            parameter=parameter,
            errors=errors,
            content={
                "value": value,
                "numerator": numerator,
                "denominator": denominator,
                "parameter_type": parameter_type,
                "method": method,
                "value_type": value_type,
                "statistical_approach": statistical_approach,
            }
        )
