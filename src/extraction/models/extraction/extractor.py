# src/extraction/models/extraction/extractor.py
from dataclasses import dataclass
from typing import Optional, List
import logging

from .tools import (
    MODEL_TYPES, COMPARTMENTAL_TYPES, STOCH_DETER,
    TRANSMISSION_ROUTES, ASSUMPTIONS, INTERVENTIONS,
    CODING_LANGUAGES, DATA_AVAILABILITY
)

logger = logging.getLogger(__name__)


@dataclass
class ModelExtractionResult:
    success: bool
    message: str
    errors: list[str]
    content: dict


@dataclass
class ModelProvenanceResult:
    success: bool
    message: str
    errors: list[str]
    content: dict


class ModelExtractor:
    
    MODEL_TYPES = MODEL_TYPES
    COMPARTMENTAL_TYPES = COMPARTMENTAL_TYPES
    STOCH_DETER = STOCH_DETER
    TRANSMISSION_ROUTES = TRANSMISSION_ROUTES
    ASSUMPTIONS = ASSUMPTIONS
    INTERVENTIONS = INTERVENTIONS
    CODING_LANGUAGES = CODING_LANGUAGES
    DATA_AVAILABILITY = DATA_AVAILABILITY
    
    def validate_model(
        self,
        model_type: str,
        compartmental_type: str,
        transmission_route: List[str],
        assumptions: List[str],
        theoretical_model: bool,
        interventions_type: List[str],
        code_available: bool,
        stoch_deter: Optional[str] = None,
        uncertainty_was_considered: Optional[bool] = None,
        spatial_model: Optional[bool] = None,
        spillover_included: Optional[bool] = None,
        coding_language: Optional[str] = None,
        is_data_used_available: Optional[str] = None,
        readme_included: Optional[bool] = None,
        notes: Optional[str] = None,
        **kwargs
    ) -> ModelExtractionResult:
        errors = []
        
        if not model_type:
            errors.append("model_type is required and cannot be empty")
        elif model_type not in self.MODEL_TYPES:
            errors.append(f"Invalid model_type '{model_type}'. Must be one of: {self.MODEL_TYPES}")
        
        if not compartmental_type:
            errors.append("compartmental_type is required and cannot be empty")
        elif compartmental_type not in self.COMPARTMENTAL_TYPES:
            errors.append(f"Invalid compartmental_type '{compartmental_type}'. Must be one of: {self.COMPARTMENTAL_TYPES}")
        
        if stoch_deter and stoch_deter not in self.STOCH_DETER:
            errors.append(f"Invalid stoch_deter '{stoch_deter}'. Must be one of: {self.STOCH_DETER}")
        
        if not transmission_route:
            errors.append("transmission_route is required and cannot be empty")
        for route in transmission_route:
            if route not in self.TRANSMISSION_ROUTES:
                errors.append(f"Invalid transmission_route '{route}'. Must be one of: {self.TRANSMISSION_ROUTES}")

        if not assumptions:
            errors.append("assumptions is required and cannot be empty")
        for assumption in assumptions:
            if assumption not in self.ASSUMPTIONS:
                errors.append(f"Invalid assumption '{assumption}'. Must be one of: {self.ASSUMPTIONS}")
        
        if not interventions_type:
            errors.append("interventions_type is required and cannot be empty")
        for intervention in interventions_type:
            if intervention not in self.INTERVENTIONS:
                errors.append(f"Invalid intervention '{intervention}'. Must be one of: {self.INTERVENTIONS}")
        
        if coding_language and coding_language not in self.CODING_LANGUAGES:
            errors.append(f"Invalid coding_language '{coding_language}'. Must be one of: {self.CODING_LANGUAGES}")
        
        if is_data_used_available and is_data_used_available not in self.DATA_AVAILABILITY:
            errors.append(f"Invalid is_data_used_available '{is_data_used_available}'. Must be one of: {self.DATA_AVAILABILITY}")
        
        if model_type != "Compartmental" and compartmental_type != "Not compartmental":
            errors.append("Non-compartmental model_type should have 'Not compartmental' as compartmental_type")
        
        content = {
            "model_type": model_type,
            "compartmental_type": compartmental_type,
            "stoch_deter": stoch_deter,
            "transmission_route": ";".join(transmission_route),
            "uncertainty_was_considered": uncertainty_was_considered,
            "spatial_model": spatial_model,
            "spillover_included": spillover_included,
            "assumptions": ";".join(assumptions),
            "theoretical_model": theoretical_model,
            "interventions_type": ";".join(interventions_type),
            "code_available": code_available,
            "coding_language": coding_language,
            "is_data_used_available": is_data_used_available,
            "readme_included": readme_included,
            "notes": notes,
        }
        
        success = len(errors) == 0
        message = "Validation successful." if success else "Errors:\n" + "\n".join([f"- {e}" for e in errors])
        
        return ModelExtractionResult(success=success, message=message, errors=errors, content=content)
    
    def validate_provenance(
        self,
        model_type_excerpt: str,
        compartmental_type_excerpt: str,
        stoch_deter_excerpt: Optional[str],
        transmission_route_excerpts: List[dict],
        assumptions_excerpts: List[dict],
        interventions_type_excerpts: List[dict],
        coding_language_excerpt: Optional[str],
        data_availability_excerpt: Optional[str],
        extracted_values: Optional[dict] = None,
        **kwargs
    ) -> ModelProvenanceResult:
        errors = []
        
        if extracted_values:
            extracted_transmission_routes = set(extracted_values.get("transmission_route", "").split(";"))
            provenance_transmission_routes = set(e["value"] for e in transmission_route_excerpts)
            if extracted_transmission_routes != provenance_transmission_routes:
                errors.append(f"Mismatch in transmission_route: extracted {extracted_transmission_routes} but provenance has {provenance_transmission_routes}")
            
            extracted_assumptions = set(extracted_values.get("assumptions", "").split(";"))
            provenance_assumptions = set(e["value"] for e in assumptions_excerpts)
            if extracted_assumptions != provenance_assumptions:
                errors.append(f"Mismatch in assumptions: extracted {extracted_assumptions} but provenance has {provenance_assumptions}")
            
            extracted_interventions = set(extracted_values.get("interventions_type", "").split(";"))
            provenance_interventions = set(e["value"] for e in interventions_type_excerpts)
            if extracted_interventions != provenance_interventions:
                errors.append(f"Mismatch in interventions_type: extracted {extracted_interventions} but provenance has {provenance_interventions}")
        
        content = {
            "model_type_excerpt": model_type_excerpt,
            "compartmental_type_excerpt": compartmental_type_excerpt,
            "stoch_deter_excerpt": stoch_deter_excerpt,
            "transmission_route_excerpts": {e["value"]: e["excerpt"] for e in transmission_route_excerpts},
            "assumptions_excerpts": {e["value"]: e["excerpt"] for e in assumptions_excerpts},
            "interventions_type_excerpts": {e["value"]: e["excerpt"] for e in interventions_type_excerpts},
            "coding_language_excerpt": coding_language_excerpt,
            "data_availability_excerpt": data_availability_excerpt,
        }
        
        success = len(errors) == 0
        message = "Provenance validation successful." if success else "Provenance errors:\n" + "\n".join([f"- {e}" for e in errors])
        
        return ModelProvenanceResult(success=success, message=message, errors=errors, content=content)
