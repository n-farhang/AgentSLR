# src/extraction/parameters/extraction/tools/extractor.py
import uuid

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from pandas import array

@dataclass
class ParameterExtractionResult(ABC):
    parameter: str
    success: bool
    message: str
    errors: list[str]
    content: dict

class ParameterExtractor:
    POPULATION_SEXES = ["Male", "Female", "Both", "Unspecified"]
    POPULATION_SAMPLE_TYPES = [
        "Community based",
        "Hospital based",
        "Household based",
        "Housing estate based",
        "Population based",
        "School based",
        "Travel based",
        "Trade / business based",
        "Contact based",
        "Other",
        "Mixed settings",
        "Unspecified",
    ]
    POPULATION_GROUPS = [
        "Healthcare workers",
        "Farmers",
        "Outdoor workers",
        "Animal workers",
        "Butchers",
        "Abattoir workers",
        "Pregnant women",
        "Children",
        "Sex workers",
        "People who inject drugs",
        "Household contacts of survivors",
        "Persons under investigation",
        "General population",
        "Mixed groups",
        "Persons with symptoms",
        "Unspecified",
        "Other",
    ]
    VALUE_TYPES = [
        "mean",
        "median",
        "mode",
        "central",
        "maximum_likelihood",
        "shape",
        "other",
        "unspecified",
    ]
    STATISTICAL_APPROACHES = [
        "observed_sample_statistic",
        "estimated_model_parameter",
        "unspecified",
        "case_study",
    ]
    SINGLE_TYPE_UNCERTAINTIES = [
        "standard_error",
        "standard_deviation",
        "variance",
        "coefficient_of_variation",
        "other",
    ]
    PAIRED_UNCERTAINTIES = [
        "CI90%",
        "CI95%",
        "CRI90%",
        "CRI95%",
        "range",
        "IQR",
        "highest_posterior_density_interval_95%",
        "other",
    ]
    DISTRIBUTION_TYPES = [
        "Bernoulli",
        "Beta",
        "Beta-Binomial",
        "Cauchy",
        "Cauchy-half",
        "Chi-square-inverse",
        "Dirichlet",
        "Exponential",
        "Gamma",
        "Gamma-inverse",
        "LKJ",
        "Multinomial",
        "Negative-Binomial",
        "Normal",
        "Normal-Log",
        "Normal-Logit",
        "Normal-Multivariate",
        "Poisson",
        "Student-t",
        "Student-t_Multivariate",
        "Uniform",
        "Uniform-Discrete",
        "Weibull",
        "Wishart-Inverse",
    ]

    SUMMARY_TOOL_CALL = {
        "type": "function",
        "function": {
            "name": "extract_parameter_summaries",
            "description": (
                "Extract summaries about parameter estimates found in the input text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summaries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "value_info": {
                                    "type": "string",
                                    "description": "Information about the value of the parameter, including units and uncertainty bounds."
                                },
                                "population_info": {
                                    "type": "string",
                                    "description": "Information about the study population of the parameter. This must include demographic details such as age, sex, and sample size, as well as the location where the study was conducted, if provided."
                                }
                            },
                            "required": ["value_info", "population_info"]
                        },
                        "description": "A list of summaries about parameter estimates found in the input text."
                    }
                },
                "required": ["summaries"]
            }
        }
    }

    SCREENING_TOOL_CALL = {
        "type": "function",
        "function": {
            "name": "screen_parameter",
            "description": (
                "Report whether the article contains estimates of the specified parameter type."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contains_parameter": {
                        "type": "boolean",
                        "description": (
                            "True if the article estimates parameters of the specified type, "
                            "False otherwise."
                        )
                    },
                    "annotations": {
                        "type": ["string", "null"],
                        "description": (
                            "If contains_parameter is True, provide the relevant text excerpt "
                            "for the first parameter you found. If False, set to null."
                        )
                    }
                },
                "required": ["contains_parameter", "annotations"]
            }
        }
    }

    UNCERTAINTY_TOOL_CALL = {
        "type": "function",
        "function": {
            "name": "extract_uncertainty_info",
            "description": (
                "Extract uncertainty information for parameters found in the input text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "value_type": {
                        "type": "string",
                        "description": (
                            "The type of value being extracted. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(VALUE_TYPES)}."
                        ),
                    },
                    "statistical_approach": {
                        "type": "string",
                        "description": (
                            "The statistical approach used in the study. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(STATISTICAL_APPROACHES)}."
                        ),
                    },
                    "single_type_uncertainty": {
                        "type": ["string", "null"],
                        "description": (
                            "Single-type uncertainty is if only a standard deviation or coefficient of variation, for example, is reported rather than a range of values. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(SINGLE_TYPE_UNCERTAINTIES)}. "
                            "If not provided, set to null."
                        ),
                    },
                    "single_type_uncertainty_value": {
                        "type": ["number", "null"],
                        "description": (
                            "The value of the single-type uncertainty measure. "
                            "If not provided, set to null."
                        ),
                    },
                    "paired_uncertainty": {
                        "type": ["string", "null"],
                        "description": (
                            "Paired uncertainty is the option you will be using most of the time -- this includes confidence and credible intervals. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(PAIRED_UNCERTAINTIES)}. "
                            "If not provided, set to null."
                        ),
                    },
                    "paired_uncertainty_lower_bound": {
                        "type": ["number", "null"],
                        "description": (
                            "The lower bound of the paired uncertainty measure. "
                            "If not provided, set to null."
                        ),
                    },
                    "paired_uncertainty_upper_bound": {
                        "type": ["number", "null"],
                        "description": (
                            "The upper bound of the paired uncertainty measure. "
                            "If not provided, set to null."
                        ),
                    },
                    "distribution_type": {
                        "type": ["string", "null"],
                        "description": (
                            "Use this when a study states that the uncertainty around your value follows some distribution. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(DISTRIBUTION_TYPES)}. "
                            "If not provided, set to null."
                        ),
                    },
                },
                "required": [
                    "value_type",
                    "statistical_approach",
                    "single_type_uncertainty",
                    "single_type_uncertainty_value",
                    "paired_uncertainty",
                    "paired_uncertainty_lower_bound",
                    "paired_uncertainty_upper_bound",
                    "distribution_type"
                ]
            }
        }
    }

    POPULATION_TOOL_CALL = {
        "type": "function",
        "function": {
            "name": "extract_population_info",
            "description": (
                "Extract population information for parameters found in the input text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "population_sex": {
                        "type": "string",
                        "description": (
                            "The sex composition of your study population. If you have 99 "
                            "men and 1 woman you would still put both in this option. "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(POPULATION_SEXES)}."
                        ),
                    },
                    "population_sample_type": {
                        "type": "string",
                        "description": (
                            "How was the study conducted? "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(POPULATION_SAMPLE_TYPES)}."
                        ),
                    },
                    "population_group": {
                        "type": "string",
                        "description": (
                            "The demographic, e.g. who was tested? "
                            "Can take ONLY one of the following values: "
                            f"{', '.join(POPULATION_GROUPS)}."
                        ),
                    },
                    "population_sample_size": {
                        "type": ["integer", "null"],
                        "description": (
                            "The number of participants/samples tested. "
                            "If not provided, set to null."
                        ),
                    },
                    "population_age_min": {
                        "type": ["integer", "null"],
                        "description": (
                            "The minimum age of the study population. "
                            "If your sample is people over 18 you would set "
                            "population_age_min = 18 and set population_age_max to null. "
                            "If not provided, set to null."
                        ),
                    },
                    "population_age_max": {
                        "type": ["integer", "null"],
                        "description": (
                            "The maximum age of the study population. "
                            "If not provided, set to null."
                        ),
                    },
                    "population_country": {
                        "type": ["string", "null"],
                        "description": (
                            "The country where the study was conducted. "
                            "If not provided, set to null."
                        ),
                    },
                    "population_location": {
                        "type": ["string", "null"],
                        "description": (
                            "The specific location reported (e.g., city, region, hospital). "
                            "If not provided, set to null."
                        ),
                    },
                },
                "required": ["population_sex", "population_sample_type", "population_group"],
            }
        }
    }

    AGGREGATION_TOOL_CALL = {
        "type": "function",
        "function": {
            "name": "extract_aggregated_parameters",
            "description": (
                "Aggregate extracted parameters according to population information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "lower_bound": {
                        "type": "number",
                        "description": "The lower bound of the aggregated parameter.",
                    },
                    "upper_bound": {
                        "type": "number",
                        "description": "The upper bound of the aggregated parameter.",
                    },
                    "disaggregated_by": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": (
                            "Description of how the parameter was disaggregated by "
                            "population characteristics."
                        ),
                    },
                    "aggregated_ids": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": (
                            "UUIDs of the aggregated parameters."
                        ),
                    }
                },
                "required": [
                    "lower_bound", "upper_bound", "disaggregated_by", "aggregated_ids"
                ],
            }
        }
    }

    @property
    @abstractmethod
    def TOOL_CALL(self) -> dict:
        pass


    def extract_summaries(self, parameter: str, fulltext: str, summaries: list[dict[str, str]]) -> ParameterExtractionResult:
        errors = []
        # for excerpt in excerpts:
        #     if excerpt["value_info"] not in fulltext:
        #         errors.append(
        #             f"Excerpt not found in fulltext: {excerpt['value_info']}. "
        #             "Make sure your extracted excerpts are direct quotations from the provided text."
        #         )
        #     if excerpt["population_info"] not in fulltext:
        #         errors.append(
        #             f"Excerpt not found in fulltext: {excerpt['population_info']}. "
        #             "Make sure your extracted excerpts are direct quotations from the provided text."
        #         )

        return self.return_result(
            parameter=parameter,
            errors=errors,
            content={"excerpts": summaries}
        )

    def extract_screening(
        self,
        parameter: str,
        contains_parameter: bool,
        annotations: Optional[str],
    ) -> ParameterExtractionResult:
        errors = []

        if contains_parameter and annotations is None:
            errors.append(
                "When contains_parameter is True, you must provide annotations "
                "with the relevant text excerpt."
            )

        return self.return_result(
            parameter=parameter,
            errors=errors,
            content={
                "contains_parameter": contains_parameter,
                "annotations": annotations,
            }
        )

    def return_result(
        self,
        parameter: str,
        errors: list[str],
        content: dict = {},
    ) -> ParameterExtractionResult:

        success = len(errors) == 0

        if success:
            message = f"{parameter} submitted successfully."
        else:
            message = (
                f"Errors in extracting {parameter} parameter:\n"
                "\n".join([f"- {msg}" for msg in errors])
            )

        return ParameterExtractionResult(
            parameter=parameter,
            success=success,
            message=message,
            errors=errors,
            content=content,
        )

    @abstractmethod
    def extract_value(self, parameter: str, **kwargs) -> ParameterExtractionResult:
        pass

    def extract_uncertainty_info(
        self,
        parameter: str,
        value_type: str,
        statistical_approach: str,
        single_type_uncertainty: Optional[str],
        single_type_uncertainty_value: Optional[float],
        paired_uncertainty: Optional[str],
        paired_uncertainty_lower_bound: Optional[float],
        paired_uncertainty_upper_bound: Optional[float],
        distribution_type: Optional[str],
    ) -> ParameterExtractionResult:
        errors = []

        if value_type is not None and value_type not in self.VALUE_TYPES:
            errors.append(
                f"Invalid value_type '{value_type}'. "
                f"Allowed values are: {self.VALUE_TYPES}"
            )
        if (
            statistical_approach is not None and
            statistical_approach not in self.STATISTICAL_APPROACHES
        ):
            errors.append(
                f"Invalid statistical_approach '{statistical_approach}'. "
                f"Allowed values are: {self.STATISTICAL_APPROACHES}"
            )
        if (
            single_type_uncertainty is not None and
            single_type_uncertainty not in self.SINGLE_TYPE_UNCERTAINTIES
        ):
            errors.append(
                f"Invalid single_type_uncertainty '{single_type_uncertainty}'. "
                f"Allowed values are: {self.SINGLE_TYPE_UNCERTAINTIES}"
            )
        if (
            paired_uncertainty is not None and
            paired_uncertainty not in self.PAIRED_UNCERTAINTIES
        ):
            errors.append(
                f"Invalid paired_uncertainty '{paired_uncertainty}'. "
                f"Allowed values are: {self.PAIRED_UNCERTAINTIES}"
            )
        if (
            distribution_type is not None and
            distribution_type not in self.DISTRIBUTION_TYPES
        ):
            errors.append(
                f"Invalid distribution_type '{distribution_type}'. "
                f"Allowed values are: {self.DISTRIBUTION_TYPES}"
            )

        return self.return_result(
            parameter=parameter,
            errors=errors,
            content={
                "value_type": value_type,
                "statistical_approach": statistical_approach,
                "single_type_uncertainty": single_type_uncertainty,
                "single_type_uncertainty_value": single_type_uncertainty_value,
                "paired_uncertainty": paired_uncertainty,
                "paired_uncertainty_lower_bound": paired_uncertainty_lower_bound,
                "paired_uncertainty_upper_bound": paired_uncertainty_upper_bound,
                "distribution_type": distribution_type,
            }
        )

    def extract_population_info(
        self,
        parameter: str,
        population_sex: str,
        population_sample_type: str,
        population_group: str,
        population_sample_size: Optional[int],
        population_age_min: Optional[int],
        population_age_max: Optional[int],
        population_country: Optional[str],
        population_location: Optional[str],
    ) -> ParameterExtractionResult:
        errors = []

        if population_sex is not None and population_sex not in self.POPULATION_SEXES:
            errors.append(
                f"Invalid population sex '{population_sex}'. "
                f"Allowed values are: {self.POPULATION_SEXES}"
            )
        if (
            population_sample_type is not None and
            population_sample_type not in self.POPULATION_SAMPLE_TYPES
        ):
            errors.append(
                f"Invalid population sample type '{population_sample_type}'. "
                f"Allowed values are: {self.POPULATION_SAMPLE_TYPES}"
            )
        if (
            population_group is not None and
            population_group not in self.POPULATION_GROUPS
        ):
            errors.append(
                f"Invalid population group '{population_group}'. "
                f"Allowed values are: {self.POPULATION_GROUPS}"
            )

        return self.return_result(
            parameter=parameter,
            errors=errors,
            content={
                "population_sex": population_sex,
                "population_sample_size": population_sample_size,
                "population_sample_type": population_sample_type,
                "population_group": population_group,
                "population_age_min": population_age_min,
                "population_age_max": population_age_max,
                "population_country": population_country,
                "population_location": population_location,
            }
        )

    def extract_aggregated_parameters(
        self,
        parameter: str,
        lower_bound: float,
        upper_bound: float,
        disaggregated_by: list[str],
        aggregated_ids: list[str],
    ) -> ParameterExtractionResult:
        errors = []

        if lower_bound > upper_bound:
            errors.append(
                "Invalid bounds: lower_bound cannot be greater than upper_bound."
            )
        for id in aggregated_ids:
            # Check that id is a valid UUID
            try:
                _ = uuid.UUID(id)
            except ValueError:
                errors.append(f"Invalid parameter id: {id}. Must be a valid UUID.")

        return self.return_result(
            parameter=parameter,
            errors=errors,
            content={
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "disaggregated_by": disaggregated_by,
                "aggregated_ids": aggregated_ids,
            }
        )
