# src/extraction/parameters/extraction_responses_api/tools/mutation_rate/extractor.py
from ..extractor import (
    ParameterExtractionResult, ParameterExtractor
)

class MutationRateExtractor(ParameterExtractor):
    PARAMETER_TYPES = [
        "substitution_rate", "evolutionary_rate", "mutation_rate"
    ]

    UNITS = [
        "substitutions_per_site_per_year",
        "mutations_per_genome_per_generation",
        "percentage",
        "unspecified",
    ]

    @property
    def TOOL_CALL(self) -> dict:
        return {
            "type": "function",
            "name": "extract_mutation_rate_value",
            "description": (
                "Extract human delay parameter values from the provided article text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": "The value of the mutation rate parameter.",
                    },
                    "parameter_type": {
                        "type": "string",
                        "description": (
                            "The specific mutation rate parameter reported. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(self.PARAMETER_TYPES)}."
                        )
                    },
                    "unit": {
                        "type": "string",
                        "description": (
                            "The unit of the mutation rate parameter value. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(self.UNITS)}."
                        )
                    },
                    "genome_site": {
                        "type": "string",
                        "description": (
                            "The specific genome site or region associated with "
                            "the mutation rate value."
                        )
                    },
                },
                "required": ["value", "parameter_type", "genome_site"],
            },
        }


    def extract_value(
        self,
        parameter: str,
        parameter_type: str,
        value: float,
        unit: str,
        genome_site: str
    ) -> ParameterExtractionResult:
        errors = []

        if parameter_type not in self.PARAMETER_TYPES:
            errors.append(
                f"Invalid parameter_type '{parameter_type}'. "
                f"Allowed parameter_type values are: {self.PARAMETER_TYPES}"
            )

        return self.return_result(
            parameter=parameter,
            errors=errors,
            content={
                "parameter_type": parameter_type,
                "value": value,
                "unit": unit,
                "genome_site": genome_site,
            }
        )
