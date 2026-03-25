# src/extraction/parameters/extraction_responses_api/tools/relative_contribution/extractor.py
from ..extractor import (
    ParameterExtractionResult, ParameterExtractor
)


class RelativeContributionExtractor(ParameterExtractor):
    TYPES = ["human_to_human", "zoonotic_to_human"]

    @property
    def TOOL_CALL(self) -> dict:
        return {
            "type": "function",
            "name": "extract_relative_contribution_value",
            "description": (
                "Extract relative contribution parameter values from the provided article text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": (
                            "The value of the relative contribution."
                        ),
                    },
                    "type": {
                        "type": "string",
                        "description": (
                            "The type of transmission for the relative contribution. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(self.TYPES)}."
                        ),
                    },
                },
                "required": ["value", "type"],
            },
        }

    def extract_value(
        self, parameter: str, value: float, type: str
    ) -> ParameterExtractionResult:
        errors = []
        if type not in self.TYPES:
            errors.append(
                f"Invalid relative contribution type '{type}'. "
                f"Allowed types are: {self.TYPES}"
            )

        return self.return_result(
            parameter=parameter,
            errors=errors,
            content={
                "value": value,
                "type": type,
            }
        )
