# src/extraction/models/extraction_responses_api/tools.py
"""
Tool call definitions for model extraction.

This module defines the JSON schema for the model extraction tool call.
"""

MODEL_TYPES = ['Compartmental', 'Branching process', 'Agent / Individual based', 'Other', 'Unspecified']

COMPARTMENTAL_TYPES = ['SIS', 'SIR', 'SEIR', 'SEIR-SEI', 'SAIR-SEI', 'Not compartmental', 'Other compartmental']

STOCH_DETER = ['Stochastic', 'Deterministic']

TRANSMISSION_ROUTES = ['Airborne or close contact', 'Human to human (direct contact)', 'Human to human (direct non-sexual contact)', 'Vector/Animal to human', 'Sexual', 'Unspecified']

ASSUMPTIONS = ['Homogeneous mixing', 'Latent period is same as incubation period', 'Heterogenity in transmission rates - between human groups', 'Heterogenity in transmission rates - between groups', 'Heterogenity in transmission rates - between human and vector', 'Heterogenity in transmission rates - over time', 'Age dependent susceptibility', 'Cross-immunity between Zika and dengue', 'Other', 'Unspecified']

INTERVENTIONS = ['Vaccination', 'Quarantine', 'Vector/Animal control', 'Treatment', 'Contact tracing', 'Hospitals', 'Treatment centres', 'Safe burials', 'Behaviour changes', 'Wolbachia replacement', 'Wolbachia suppression', 'Genetically modified mosquitoes', 'Mechanical removal of breeding sites', 'Pesticides/larvicides', 'Insecticide-treated nets', 'Indoor residual spraying', 'Other', 'Unspecified']

CODING_LANGUAGES = ['R', 'Python', 'Matlab', 'Julia', 'C++', 'Other']

DATA_AVAILABILITY = ['Yes - as an attachment', 'Yes - with a DOI', 'Yes - on Github', 'Yes - on another platform', 'Not available', 'Unspecified']


MODEL_TOOL_CALL = {
    "type": "function",
    "name": "extract_model_data",
    "description": f"""Extract characteristics for a single model. Call this function once per model identified in the article.

We are filling out one model data form per model. Only transmission_route, assumptions, and interventions_type are multiple-select; all other fields are single-select.

We are only considering dynamic transmission models. Do not include regression-only analyses for forecasting or other models where transmission is not modelled mechanistically.

Allowed values:
- model_type: {MODEL_TYPES}
- compartmental_type: {COMPARTMENTAL_TYPES}
- stoch_deter: {STOCH_DETER}
- transmission_route: {TRANSMISSION_ROUTES}
- assumptions: {ASSUMPTIONS}
- interventions_type: {INTERVENTIONS}
- coding_language: {CODING_LANGUAGES} or null
- is_data_used_available: {DATA_AVAILABILITY} or null""",
    "strict": True,
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "model_type": {
                "type": "string",
                "enum": MODEL_TYPES,
                "description": "Type of model used. Select from compartmental, branching process (or renewal equation), agent-individual based, other or unspecified."
            },
            "compartmental_type": {
                "type": "string",
                "enum": COMPARTMENTAL_TYPES,
                "description": "Compartmental structure. If model is compartmental but not SIS, SIR, SEIR, or SEIR-SEI (for vector/animal-human models only), select other. Use 'Not compartmental' for non-compartmental models."
            },
            "stoch_deter": {
                "type": ["string", "null"],
                "enum": STOCH_DETER + [None],
                "description": "Stochastic or deterministic. Only extract if explicitly stated in the paper. Null if not specified."
            },
            "transmission_route": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "string",
                    "enum": TRANSMISSION_ROUTES
                },
                "description": "Transmission route(s) modeled. Tick all that apply from: airborne or close contact (no direct contact), human to human (direct contact), vector/animal to human, sexual, unspecified."
            },
            "uncertainty_was_considered": {
                "type": ["boolean", "null"],
                "description": "Is there evidence of uncertainty being considered in the model? This could be: if the model is stochastic; if multiple models were considered; are different values for the same parameter considered (e.g. sensitivity analyses, Bayesian analysis via prior distribution). Null if not specified."
            },
            "spatial_model": {
                "type": ["boolean", "null"],
                "description": "Does the model have a spatial component? Null if not specified."
            },
            "spillover_included": {
                "type": ["boolean", "null"],
                "description": "Does the model explicitly model spillover, e.g. by including an animal reservoir component, contribution to the force of infection from zoonosis? Null if not specified."
            },
            "assumptions": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "string",
                    "enum": ASSUMPTIONS
                },
                "description": "Model assumptions. There may be numerous assumptions, extract all of them. Assumptions should be described explicitly, this can include assumptions that are clear from any model equations (e.g. homogeneous mixing). Do not infer assumptions that are not clearly defined. If none are specified in the article, use ['Unspecified']."
            },
            "theoretical_model": {
                "type": "boolean",
                "description": "Tick this when the model was not fitted to data. Do not extract parameters from papers where they are not fitting the model to data. True if parameters NOT fitted to data (from literature/arbitrary). False if fitted to actual data."
            },
            "interventions_type": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "string",
                    "enum": INTERVENTIONS
                },
                "description": "Intervention(s) modeled. There may be multiple interventions implemented in the model. Please tick all that apply. If no interventions are modeled, use ['Unspecified']."
            },
            "code_available": {
                "type": "boolean",
                "description": "Is model code available?"
            },
            "coding_language": {
                "type": ["string", "null"],
                "enum": CODING_LANGUAGES + [None],
                "description": "Programming language used. Choose from R, Python, Matlab, Julia, C++, other. Null if not specified."
            },
            "is_data_used_available": {
                "type": ["string", "null"],
                "enum": DATA_AVAILABILITY + [None],
                "description": "Data availability status. Choose from yes (as an attachment, with a DOI, on github, on another platform), not available or unspecified. Null if not specified."
            },
            "readme_included": {
                "type": ["boolean", "null"],
                "description": "Is README included with code? Null if not applicable."
            },
            "notes": {
                "type": ["string", "null"],
                "description": "Additional context about this model."
            }
        },
        "required": [
            "model_type",
            "compartmental_type",
            "stoch_deter",
            "transmission_route",
            "uncertainty_was_considered",
            "spatial_model",
            "spillover_included",
            "assumptions",
            "theoretical_model",
            "interventions_type",
            "code_available",
            "coding_language",
            "is_data_used_available",
            "readme_included",
            "notes"
        ]
    }
}


PROVENANCE_TOOL_CALL = {
    "type": "function",
    "name": "extract_model_provenance",
    "description": "Extract excerpts from the article that support each extracted model characteristic. Provide direct quotes that justify each value selected for a specific model.",
    "strict": True,
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "model_type_excerpt": {
                "type": "string",
                "description": "Direct quote from the article supporting the model type."
            },
            "compartmental_type_excerpt": {
                "type": "string",
                "description": "Direct quote from the article supporting the compartmental type."
            },
            "stoch_deter_excerpt": {
                "type": ["string", "null"],
                "description": "Direct quote from the article supporting the stochastic/deterministic classification. Null if not specified."
            },
            "transmission_route_excerpts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "string",
                            "enum": TRANSMISSION_ROUTES,
                            "description": "The transmission route value extracted."
                        },
                        "excerpt": {
                            "type": "string",
                            "description": "Direct quote from the article supporting this transmission route."
                        }
                    },
                    "required": ["value", "excerpt"],
                    "additionalProperties": False
                },
                "description": "Excerpts supporting each transmission_route value extracted."
            },
            "assumptions_excerpts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "string",
                            "enum": ASSUMPTIONS,
                            "description": "The assumption value extracted."
                        },
                        "excerpt": {
                            "type": "string",
                            "description": "Direct quote or equation from the article supporting this assumption."
                        }
                    },
                    "required": ["value", "excerpt"],
                    "additionalProperties": False
                },
                "description": "Excerpts supporting each assumption value extracted."
            },
            "interventions_type_excerpts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "string",
                            "enum": INTERVENTIONS,
                            "description": "The intervention type value extracted."
                        },
                        "excerpt": {
                            "type": "string",
                            "description": "Direct quote from the article supporting this intervention."
                        }
                    },
                    "required": ["value", "excerpt"],
                    "additionalProperties": False
                },
                "description": "Excerpts supporting each interventions_type value extracted."
            },
            "coding_language_excerpt": {
                "type": ["string", "null"],
                "description": "Direct quote from the article mentioning the coding language. Null if not specified."
            },
            "data_availability_excerpt": {
                "type": ["string", "null"],
                "description": "Direct quote from the article supporting the data availability status. Null if not specified."
            }
        },
        "required": [
            "model_type_excerpt",
            "compartmental_type_excerpt",
            "stoch_deter_excerpt",
            "transmission_route_excerpts",
            "assumptions_excerpts",
            "interventions_type_excerpts",
            "coding_language_excerpt",
            "data_availability_excerpt"
        ]
    }
}
