# src/extraction/parameters/extraction/tools/growth_rate/extractor.py
from ..extractor import (
    ParameterExtractionResult, ParameterExtractor
)
from typing import Optional


class GrowthRateExtractor(ParameterExtractor):
    UNITS = ["per_day", "per_week", "other_or_unspecified"]

    @property
    def TOOL_CALL(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "extract_growth_rate_value",
                "description": (
                    "Extract growth rate parameter values from the provided article text."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "number",
                            "description": (
                                "The value of the growth rate."
                            ),
                        },
                        "unit": {
                            "type": "string",
                            "description": (
                                "The unit of the provided growth rate. "
                                "Can take ONLY one of the following values: "
                                f"{', '.join(self.UNITS)}."
                            ),
                        }
                    },
                    "required": ["value", "unit"],
                }
            }
        }

    def extract_value(
        self,
        parameter: str,
        value: float,
        unit: str,
    ) -> ParameterExtractionResult:
        errors = []
        if unit not in self.UNITS:
            errors.append(
                f"Invalid growth rate unit '{unit}'. "
                f"Allowed units are: {self.UNITS}"
            )

        return self.return_result(
            parameter="growth_rate",
            errors=errors,
            content={
                "value": value,
                "unit": unit,
            }
        )
