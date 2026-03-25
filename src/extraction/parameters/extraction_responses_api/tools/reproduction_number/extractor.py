# src/extraction/parameters/extraction_responses_api/tools/reproduction_number/extractor.py
from ..extractor import (
    ParameterExtractionResult, ParameterExtractor
)


class ReproductionNumberExtractor(ParameterExtractor):
    TYPES = ["basic_R0", "effective_Re"]
    TRANSMISSIONS = ["human", "mosquito", "unspecified", "other"]
    METHODS = [
        "branching_process",
        "growth_rate",
        "compartmental_model",
        "next_generation_matrix",
        "empirical",
        "genomic",
        "other",
    ]

    @property
    def TOOL_CALL(self) -> dict:
        return {
            "type": "function",
            "name": "extract_reproduction_number_value",
            "description": (
                "Extract reproduction number parameter values from the provided article text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": (
                            "The value of the reproduction number."
                        ),
                    },
                    "type": {
                        "type": "string",
                        "description": (
                            "The type of reproduction number. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(self.TYPES)}."
                        ),
                    },
                    "transmission": {
                        "type": "string",
                        "description": (
                            "The transmission mode for the reproduction number. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(self.TRANSMISSIONS)}."
                        ),
                    },
                    "method": {
                        "type": "string",
                        "description": (
                            "The method used to estimate the reproduction number. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(self.METHODS)}."
                        ),
                    },
                },
                "required": ["value", "type", "transmission", "method"],
            },
        }

    def extract_value(
        self, parameter: str, value: float, type: str, transmission: str, method: str
    ) -> ParameterExtractionResult:
        errors = []

        if type not in self.TYPES:
            errors.append(
                f"Invalid reproduction number type '{type}'. "
                f"Allowed types are: {self.TYPES}"
            )
        if transmission not in self.TRANSMISSIONS:
            errors.append(
                f"Invalid transmission mode '{transmission}'. "
                f"Allowed transmissions are: {self.TRANSMISSIONS}"
            )
        if method not in self.METHODS:
            errors.append(
                f"Invalid method '{method}'. "
                f"Allowed methods are: {self.METHODS}"
            )

        return self.return_result(
            parameter=parameter,
            errors=errors,
            content={
                "value": value,
                "type": type,
                "transmission": transmission,
                "method": method,
            }
        )
