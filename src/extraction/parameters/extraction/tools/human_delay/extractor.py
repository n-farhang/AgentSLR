# src/extraction/parameters/extraction/tools/human_delay/extractor.py
from ..extractor import (
    ParameterExtractionResult, ParameterExtractor
)
from typing import Optional

class HumanDelayExtractor(ParameterExtractor):
    DELAY_TYPES = [
        "admission__to__death",
        "admission__to__discharge_or_recovery",
        "generation_time",
        "incubation_period",
        "infectious_period",
        "other",
        "serial_interval",
        "symptom_onset__to__admission",
        "symptom_onset__to__death",
        "symptom_onset__to__discharge_or_recovery",
        "time_in_care",
    ]
    UNITS = ["hours", "days", "weeks", "other"]

    @property
    def TOOL_CALL(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "extract_human_delay_value",
                "description": (
                    "Extract human delay parameter values from the provided article text."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "number",
                            "description": "The value of the human delay parameter.",
                        },
                        "delay_type": {
                            "type": "string",
                            "description": (
                                "The specific delay parameter reported. "
                                "Can take ONLY one of the following values: "
                                f"{', '.join(self.DELAY_TYPES)}."
                            )
                        },
                        "unit": {
                            "type": "string",
                            "description": (
                                "The unit of the provided growth rate. "
                                "Can take ONLY one of the following values: "
                                f"{', '.join(self.UNITS)}."
                            ),
                        },
                        "delay_type_note": {
                            "type": ["string", "null"],
                            "description": (
                                "The specific delay type reported, if `delay_type` is set to "
                                "`other`. If this is not the case, set to null."
                            )
                        },
                    },
                    "required": ["value", "delay_type", "unit"],
                }
            }
        }

    def extract_value(
        self,
        parameter: str,
        value: float,
        delay_type: str,
        delay_type_note: Optional[str],
        unit: str
    ) -> ParameterExtractionResult:
        errors = []
        if delay_type not in self.DELAY_TYPES:
            errors.append(
                f"Invalid delay_type '{delay_type}'. "
                f"Allowed delay_type values are: {self.DELAY_TYPES}"
            )

        if delay_type_note is not None and delay_type != "other":
            errors.append(
                "delay_type_note was set, but delay_type is not set to 'other'. "
                "Only set delay_type_note to a non-null value if delay_type = 'other'."
            )

        if unit not in self.UNITS:
            errors.append(
                f"Invalid human delay unit '{unit}'. "
                f"Allowed units are: {self.UNITS}"
            )

        return self.return_result(
            parameter=parameter,
            errors=errors,
            content={
                "value": value,
                "delay_type": delay_type,
                "delay_type_note": delay_type_note,
                "unit": unit,
            }
        )
