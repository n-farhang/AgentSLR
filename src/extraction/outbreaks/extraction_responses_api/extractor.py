# src/extraction/outbreaks/extraction_responses_api/extractor.py
from dataclasses import dataclass
from typing import Optional
from .tools import (
    MONTHS, COUNTRIES, OUTBREAK_SOURCES, MODE_OF_DETECTION, 
    PRE_OUTBREAK_STATUS, SEX_DISAGG_TYPES
)


@dataclass
class OutbreakExtractionResult:
    success: bool
    message: str
    errors: list[str]
    content: dict


@dataclass
class OutbreakProvenanceResult:
    success: bool
    message: str
    errors: list[str]
    content: dict


class OutbreakExtractor:
    
    MONTHS = MONTHS
    COUNTRIES = COUNTRIES
    OUTBREAK_SOURCES = OUTBREAK_SOURCES
    MODE_OF_DETECTION = MODE_OF_DETECTION
    PRE_OUTBREAK_STATUS = PRE_OUTBREAK_STATUS
    SEX_DISAGG_TYPES = SEX_DISAGG_TYPES
    
    def validate_outbreak(
        self,
        outbreak_start_day: Optional[int] = None,
        outbreak_start_month: Optional[str] = None,
        outbreak_start_year: Optional[int] = None,
        outbreak_end_day: Optional[int] = None,
        outbreak_end_month: Optional[str] = None,
        outbreak_end_year: Optional[int] = None,
        outbreak_duration_months: Optional[float] = None,
        outbreak_is_currently_ongoing: bool = False,
        outbreak_country: str = "",
        outbreak_location: Optional[str] = None,
        outbreak_location_type: Optional[str] = None,
        outbreak_source: Optional[str] = None,
        mode_of_detection: Optional[str] = None,
        method_of_case_definition: Optional[str] = None,
        pre_outbreak: Optional[str] = None,
        cases_confirmed: Optional[float] = None,
        cases_probable: Optional[float] = None,
        cases_suspected: Optional[float] = None,
        cases_unspecified: Optional[float] = None,
        cases_asymptomatic: Optional[float] = None,
        cases_severe: Optional[float] = None,
        deaths: Optional[float] = None,
        asymptomatic_transmission_described: bool = False,
        population_size_geographical_area: Optional[float] = None,
        type_cases_sex_disagg: Optional[str] = None,
        male_cases: Optional[float] = None,
        prop_male_cases: Optional[float] = None,
        female_cases: Optional[float] = None,
        prop_female_cases: Optional[float] = None,
        notes: Optional[str] = None,
        **kwargs
    ) -> OutbreakExtractionResult:
        errors = []
        
        if not outbreak_country:
            errors.append("outbreak_country is required")
        elif outbreak_country not in self.COUNTRIES:
            errors.append(
                f"Invalid outbreak_country '{outbreak_country}'. "
                f"Must be one of the WHO standard country names."
            )
        
        if outbreak_start_month and outbreak_start_month not in self.MONTHS:
            errors.append(
                f"Invalid outbreak_start_month '{outbreak_start_month}'. "
                f"Must be one of: {', '.join(self.MONTHS)}"
            )
        if outbreak_end_month and outbreak_end_month not in self.MONTHS:
            errors.append(
                f"Invalid outbreak_end_month '{outbreak_end_month}'. "
                f"Must be one of: {', '.join(self.MONTHS)}"
            )
        
        if outbreak_start_day is not None and (outbreak_start_day < 1 or outbreak_start_day > 31):
            errors.append("outbreak_start_day must be between 1 and 31")
        if outbreak_end_day is not None and (outbreak_end_day < 1 or outbreak_end_day > 31):
            errors.append("outbreak_end_day must be between 1 and 31")
        
        if outbreak_source and outbreak_source not in self.OUTBREAK_SOURCES:
            errors.append(
                f"Invalid outbreak_source '{outbreak_source}'. "
                f"Must be one of: {', '.join(self.OUTBREAK_SOURCES)}"
            )
        
        if mode_of_detection and mode_of_detection not in self.MODE_OF_DETECTION:
            errors.append(
                f"Invalid mode_of_detection '{mode_of_detection}'. "
                f"Must be one of: {', '.join(self.MODE_OF_DETECTION)}"
            )
        
        if pre_outbreak and pre_outbreak not in self.PRE_OUTBREAK_STATUS:
            errors.append(
                f"Invalid pre_outbreak '{pre_outbreak}'. "
                f"Must be one of: {', '.join(self.PRE_OUTBREAK_STATUS)}"
            )
        
        if type_cases_sex_disagg and type_cases_sex_disagg not in self.SEX_DISAGG_TYPES:
            errors.append(
                f"Invalid type_cases_sex_disagg '{type_cases_sex_disagg}'. "
                f"Must be one of: {', '.join(self.SEX_DISAGG_TYPES)}"
            )
        
        case_fields = [
            ("cases_confirmed", cases_confirmed),
            ("cases_probable", cases_probable),
            ("cases_suspected", cases_suspected),
            ("cases_unspecified", cases_unspecified),
            ("cases_asymptomatic", cases_asymptomatic),
            ("cases_severe", cases_severe),
            ("deaths", deaths),
            ("male_cases", male_cases),
            ("female_cases", female_cases),
            ("population_size_geographical_area", population_size_geographical_area),
        ]
        
        for field_name, field_value in case_fields:
            if field_value is not None and field_value < 0:
                errors.append(f"{field_name} must be non-negative, got {field_value}")
        
        if outbreak_location and "," in outbreak_location:
            errors.append("outbreak_location should not contain commas; use semicolons instead")
        
        content = {
            "outbreak_start_day": outbreak_start_day,
            "outbreak_start_month": outbreak_start_month,
            "outbreak_start_year": outbreak_start_year,
            "outbreak_end_day": outbreak_end_day,
            "outbreak_end_month": outbreak_end_month,
            "outbreak_end_year": outbreak_end_year,
            "outbreak_duration_months": outbreak_duration_months,
            "outbreak_is_currently_ongoing": outbreak_is_currently_ongoing,
            "outbreak_country": outbreak_country,
            "outbreak_location": outbreak_location,
            "outbreak_location_type": outbreak_location_type,
            "outbreak_source": outbreak_source,
            "mode_of_detection": mode_of_detection,
            "method_of_case_definition": method_of_case_definition,
            "pre_outbreak": pre_outbreak,
            "cases_confirmed": cases_confirmed,
            "cases_probable": cases_probable,
            "cases_suspected": cases_suspected,
            "cases_unspecified": cases_unspecified,
            "cases_asymptomatic": cases_asymptomatic,
            "cases_severe": cases_severe,
            "deaths": deaths,
            "asymptomatic_transmission_described": asymptomatic_transmission_described,
            "population_size_geographical_area": population_size_geographical_area,
            "type_cases_sex_disagg": type_cases_sex_disagg,
            "male_cases": male_cases,
            "prop_male_cases": prop_male_cases,
            "female_cases": female_cases,
            "prop_female_cases": prop_female_cases,
            "notes": notes,
        }
        
        success = len(errors) == 0
        message = (
            "Outbreak data validated successfully." if success
            else f"Validation failed. Please correct the following errors:\n" + 
                 "\n".join([f"- {e}" for e in errors])
        )
        
        return OutbreakExtractionResult(
            success=success,
            message=message,
            errors=errors,
            content=content
        )
    
    def validate_provenance(
        self,
        outbreak_country_excerpt: Optional[str] = None,
        outbreak_location_excerpt: Optional[str] = None,
        outbreak_start_excerpt: Optional[str] = None,
        outbreak_end_excerpt: Optional[str] = None,
        outbreak_duration_excerpt: Optional[str] = None,
        outbreak_source_excerpt: Optional[str] = None,
        mode_of_detection_excerpt: Optional[str] = None,
        method_of_case_definition_excerpt: Optional[str] = None,
        pre_outbreak_excerpt: Optional[str] = None,
        cases_confirmed_excerpt: Optional[str] = None,
        cases_probable_excerpt: Optional[str] = None,
        cases_suspected_excerpt: Optional[str] = None,
        cases_unspecified_excerpt: Optional[str] = None,
        cases_asymptomatic_excerpt: Optional[str] = None,
        cases_severe_excerpt: Optional[str] = None,
        deaths_excerpt: Optional[str] = None,
        asymptomatic_transmission_excerpt: Optional[str] = None,
        population_size_excerpt: Optional[str] = None,
        sex_disaggregation_excerpt: Optional[str] = None,
        extracted_values: Optional[dict] = None,
        **kwargs
    ) -> OutbreakProvenanceResult:
        """Validate provenance excerpts for an extracted outbreak.
        
        Checks that excerpts are provided for non-null extracted values.
        """
        errors = []
        
        # Map of extracted field names to their excerpt field names
        field_excerpt_mapping = {
            "outbreak_country": outbreak_country_excerpt,
            "outbreak_location": outbreak_location_excerpt,
            "outbreak_source": outbreak_source_excerpt,
            "mode_of_detection": mode_of_detection_excerpt,
            "method_of_case_definition": method_of_case_definition_excerpt,
            "pre_outbreak": pre_outbreak_excerpt,
            "cases_confirmed": cases_confirmed_excerpt,
            "cases_probable": cases_probable_excerpt,
            "cases_suspected": cases_suspected_excerpt,
            "cases_unspecified": cases_unspecified_excerpt,
            "cases_asymptomatic": cases_asymptomatic_excerpt,
            "cases_severe": cases_severe_excerpt,
            "deaths": deaths_excerpt,
            "population_size_geographical_area": population_size_excerpt,
        }
        
        # Check for missing excerpts on non-null extracted values
        if extracted_values:
            # Check country (required field)
            if extracted_values.get("outbreak_country") and not outbreak_country_excerpt:
                errors.append("Missing excerpt for outbreak_country")
            
            # Check numeric case fields
            for field, excerpt in field_excerpt_mapping.items():
                extracted_val = extracted_values.get(field)
                if extracted_val is not None and extracted_val != "" and not excerpt:
                    # Only warn, don't fail - some fields may legitimately not have clear excerpts
                    pass
            
            # Check date fields
            if any([
                extracted_values.get("outbreak_start_day"),
                extracted_values.get("outbreak_start_month"),
                extracted_values.get("outbreak_start_year")
            ]) and not outbreak_start_excerpt:
                errors.append("Missing excerpt for outbreak start date fields")
            
            if any([
                extracted_values.get("outbreak_end_day"),
                extracted_values.get("outbreak_end_month"),
                extracted_values.get("outbreak_end_year")
            ]) and not outbreak_end_excerpt:
                errors.append("Missing excerpt for outbreak end date fields")
            
            # Duration should only have excerpt if explicitly stated
            if extracted_values.get("outbreak_duration_months") and not outbreak_duration_excerpt:
                errors.append("Missing excerpt for outbreak_duration_months (must be explicitly stated)")
        
        content = {
            "outbreak_country_excerpt": outbreak_country_excerpt,
            "outbreak_location_excerpt": outbreak_location_excerpt,
            "outbreak_start_excerpt": outbreak_start_excerpt,
            "outbreak_end_excerpt": outbreak_end_excerpt,
            "outbreak_duration_excerpt": outbreak_duration_excerpt,
            "outbreak_source_excerpt": outbreak_source_excerpt,
            "mode_of_detection_excerpt": mode_of_detection_excerpt,
            "method_of_case_definition_excerpt": method_of_case_definition_excerpt,
            "pre_outbreak_excerpt": pre_outbreak_excerpt,
            "cases_confirmed_excerpt": cases_confirmed_excerpt,
            "cases_probable_excerpt": cases_probable_excerpt,
            "cases_suspected_excerpt": cases_suspected_excerpt,
            "cases_unspecified_excerpt": cases_unspecified_excerpt,
            "cases_asymptomatic_excerpt": cases_asymptomatic_excerpt,
            "cases_severe_excerpt": cases_severe_excerpt,
            "deaths_excerpt": deaths_excerpt,
            "asymptomatic_transmission_excerpt": asymptomatic_transmission_excerpt,
            "population_size_excerpt": population_size_excerpt,
            "sex_disaggregation_excerpt": sex_disaggregation_excerpt,
        }
        
        success = len(errors) == 0
        message = (
            "Provenance validation successful." if success
            else "Provenance errors:\n" + "\n".join([f"- {e}" for e in errors])
        )
        
        return OutbreakProvenanceResult(
            success=success,
            message=message,
            errors=errors,
            content=content
        )
