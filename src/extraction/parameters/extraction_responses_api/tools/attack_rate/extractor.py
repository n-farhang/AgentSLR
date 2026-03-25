# src/extraction/parameters/extraction_responses_api/tools/attack_rate/extractor.py
from ..extractor import (
    ParameterExtractionResult, ParameterExtractor
)
from typing import Optional


class AttackRateExtractor(ParameterExtractor):
    UNITS = ["percentage", "rate"]

    @property
    def TOOL_CALL(self) -> dict:
        return {
            "type": "function",
            "name": "extract_attack_rate_value",
            "description": (
                "Extract attack rate parameter values from the provided article text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": (
                            "The value of the attack rate."
                        ),
                    },
                    "unit": {
                        "type": "string",
                        "description": (
                            "The unit of the provided attack rate. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(self.UNITS)}."
                        ),
                    },
                    "rate_denominator": {
                        "type": ["integer", "null"],
                        "description": (
                            "The denominator of the rate, if the parameter is provided as "
                            "a rate. Otherwise, set to null."
                        ),
                    }
                },
                "required": ["value", "unit", "rate_denominator"],
            },
        }

    def extract_value(
        self, parameter: str, value: float, unit: str, rate_denominator: Optional[int]
    ) -> ParameterExtractionResult:
        errors = []
        if unit not in self.UNITS:
            errors.append(
                f"Invalid attack rate unit '{unit}'. "
                f"Allowed units are: {self.UNITS}"
            )

        return self.return_result(
            parameter=parameter,
            errors=errors,
            content={
                "value": value,
                "unit": unit,
                "rate_denominator": rate_denominator,
            }
        )
