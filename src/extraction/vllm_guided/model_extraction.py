# src/extraction/vllm_guided/model_extraction.py
"""
vLLM Guided JSON extraction for models.

This module provides a wrapper class that can be used with the existing
ModelExtractionRunner to extract models using grammar-constrained decoding
instead of tool calls.
"""

import json
import logging
from json.decoder import JSONDecodeError
from typing import Optional

from openai import OpenAI

from ..models.extraction.extractor import (
    ModelExtractor,
    ModelExtractionResult,
    ModelProvenanceResult,
)
from .schemas import MODEL_GUIDED_JSON_SCHEMA, MODEL_PROVENANCE_GUIDED_JSON_SCHEMA


class GuidedModelExtractor:
    """
    Extracts model data using vLLM guided JSON decoding.
    
    This class provides an alternative extraction method that uses
    grammar-constrained decoding to ensure strict schema compliance,
    rather than relying on tool/function calls.
    
    Usage:
        guided = GuidedModelExtractor(client, model_name, logger)
        extractions, trace = guided.extract_models(
            article_text, article_id, system_prompt, extraction_prompt,
            max_completion_tokens, extra_body
        )
    """
    
    def __init__(
        self,
        client: OpenAI,
        model_name: str,
        logger: Optional[logging.Logger] = None,
    ):
        self.client = client
        self.model_name = model_name
        self.logger = logger or logging.getLogger(__name__)
        self.extractor = ModelExtractor()
    
    def _convert_guided_json_to_args(self, data: dict) -> dict:
        """Convert guided JSON response to function arguments format.
        
        The guided JSON schema uses:
        - Native booleans for boolean fields
        - "null" string in enums for nullable string fields
        - Empty string for notes when no notes
        """
        model_data = data.get("model_data", data)
        
        # Convert string "null" to None for nullable enum fields
        def nullable_str(val):
            if val == "null" or val is None:
                return None
            return val
        
        # Notes: empty string means no notes
        notes = model_data.get("notes", "")
        if notes == "" or notes == "null":
            notes = None
        
        return {
            # Required string enums
            "model_type": model_data.get("model_type"),
            "compartmental_type": model_data.get("compartmental_type"),
            # Nullable string enum
            "stoch_deter": nullable_str(model_data.get("stoch_deter")),
            # Required array
            "transmission_route": model_data.get("transmission_route", []),
            # Booleans (native in schema)
            "uncertainty_was_considered": model_data.get("uncertainty_was_considered"),
            "spatial_model": model_data.get("spatial_model"),
            "spillover_included": model_data.get("spillover_included"),
            # Required array
            "assumptions": model_data.get("assumptions", []),
            # Required boolean
            "theoretical_model": model_data.get("theoretical_model"),
            # Required array
            "interventions_type": model_data.get("interventions_type", []),
            # Required boolean
            "code_available": model_data.get("code_available"),
            # Nullable string enums
            "coding_language": nullable_str(model_data.get("coding_language")),
            "is_data_used_available": nullable_str(model_data.get("is_data_used_available")),
            # Boolean
            "readme_included": model_data.get("readme_included"),
            # Free string, empty -> None
            "notes": notes,
        }
    
    def extract_models(
        self,
        article_text: str,
        article_id: str,
        system_prompt: str,
        extraction_prompt: str,
        max_completion_tokens: int = 98304,
        extra_body: Optional[dict] = None,
    ) -> tuple[list[dict], dict]:
        """
        Extract models using vLLM guided JSON decoding.
        
        Args:
            article_text: Full text of the article
            article_id: Article identifier for logging
            system_prompt: System prompt for the LLM
            extraction_prompt: Extraction instructions prompt
            max_completion_tokens: Max tokens for completion
            extra_body: Additional body params (e.g., thinking mode)
            
        Returns:
            Tuple of (list of extracted model dicts, trace dict)
        """
        import datetime as dt
        
        # Build guided-specific prompt
        guided_prompt = extraction_prompt + """

IMPORTANT: Analyze the article carefully. Your final response must be a JSON object.

For each transmission model found, output:
{"action": "extract_model", "model_data": {...}}

When you have extracted ALL models and there are no more to extract, output:
{"action": "done"}

Extract one model at a time. After each extraction, I will ask you to continue."""

        prompt = system_prompt + "\n\n" + guided_prompt

        input_list = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": article_text},
        ]

        trace = {
            "stage": "extraction_guided",
            "article_id": article_id,
            "timestamp": dt.datetime.now().isoformat(),
            "input": input_list.copy(),
            "iterations": [],
            "extractions": [],
            "error": None,
        }

        extractions = []
        max_iterations = 50
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            iteration_trace = {
                "iteration": iteration,
                "response": None,
                "parsed_json": None,
                "validation_result": None,
            }

            try:
                # Build extra_body with structured_outputs (vLLM v0.12+)
                request_extra_body = dict(extra_body) if extra_body else {}
                request_extra_body["structured_outputs"] = {"json": MODEL_GUIDED_JSON_SCHEMA}

                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=input_list,
                    reasoning_effort="high",
                    max_completion_tokens=max_completion_tokens,
                    extra_body=request_extra_body
                )

                iteration_trace["response"] = response.model_dump()

                message = response.choices[0].message
                content = message.content or ""
                
                # Capture reasoning content if present (from thinking/reasoning feature)
                reasoning_content = getattr(message, 'reasoning_content', None)
                if reasoning_content:
                    iteration_trace["reasoning"] = reasoning_content
                
                # Add assistant message to conversation
                input_list.append({"role": "assistant", "content": content})

                # Parse JSON from response - with structured_outputs, content should be pure JSON
                try:
                    parsed = json.loads(content)
                    iteration_trace["parsed_json"] = parsed
                except JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSON for article {article_id}: {e}")
                    self.logger.debug(f"Raw content: {content[:500]}")
                    # Ask for retry
                    input_list.append({
                        "role": "user",
                        "content": 'Invalid JSON. Please respond with valid JSON: either {"action": "extract_model", "model_data": {...}} or {"action": "done"}'
                    })
                    trace["iterations"].append(iteration_trace)
                    continue

                # Check if done
                action = parsed.get("action", "")
                if action == "done":
                    self.logger.info(f"Model extraction complete for article {article_id}, found {len(extractions)} models")
                    trace["iterations"].append(iteration_trace)
                    break

                if action != "extract_model" or "model_data" not in parsed:
                    input_list.append({
                        "role": "user",
                        "content": 'Please extract the next model or indicate you are done with {"action": "done"}'
                    })
                    trace["iterations"].append(iteration_trace)
                    continue

                # Convert and validate
                function_args = self._convert_guided_json_to_args(parsed)
                
                try:
                    result = self.extractor.validate_model(**function_args)
                except Exception as e:
                    self.logger.error(f"Validation error for article {article_id}: {e}")
                    result = ModelExtractionResult(
                        success=False,
                        message=f"Validation error: {e}",
                        errors=[str(e)],
                        content={},
                    )

                iteration_trace["validation_result"] = {
                    "success": result.success,
                    "message": result.message,
                    "errors": result.errors,
                }

                if result.success:
                    extraction_data = {
                        "article_id": article_id,
                        **result.content
                    }
                    extractions.append(extraction_data)
                    trace["extractions"].append(extraction_data)
                    
                    # Ask for next model
                    input_list.append({
                        "role": "user",
                        "content": "Model extracted successfully. Are there any more models to extract? If yes, extract the next one. If no, respond with {\"action\": \"done\"}"
                    })
                else:
                    self.logger.warning(f"Validation failed for model in article {article_id}: {result.message}")
                    # Ask to re-extract with corrections
                    input_list.append({
                        "role": "user",
                        "content": f"Validation failed: {result.message}. Please re-extract with corrections."
                    })

                trace["iterations"].append(iteration_trace)

            except Exception as e:
                self.logger.error(f"Error during model extraction for article {article_id}: {e}")
                iteration_trace["error"] = str(e)
                trace["iterations"].append(iteration_trace)
                trace["error"] = str(e)
                break

        return extractions, trace
    
    def extract_provenance(
        self,
        article_text: str,
        article_id: str,
        model_data: dict,
        system_prompt: str,
        max_completion_tokens: int = 98304,
        extra_body: Optional[dict] = None,
    ) -> tuple[Optional[dict], dict]:
        """
        Extract provenance (excerpts) for a model using guided JSON.
        
        Args:
            article_text: Full text of the article
            article_id: Article identifier
            model_data: The extracted model data to get provenance for
            system_prompt: System prompt
            max_completion_tokens: Max tokens
            extra_body: Additional body params
            
        Returns:
            Tuple of (provenance dict or None, trace dict)
        """
        import datetime as dt
        
        provenance_prompt = f"""Extract direct quotes from the article that support the following model extraction:

{json.dumps(model_data, indent=2)}

Provide exact quotes from the article text that justify each extracted value."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": article_text},
            {"role": "assistant", "content": f"I have extracted this model data: {json.dumps(model_data)}"},
            {"role": "user", "content": provenance_prompt}
        ]
        
        trace = {
            "stage": "provenance_guided",
            "article_id": article_id,
            "timestamp": dt.datetime.now().isoformat(),
            "response": None,
            "error": None,
        }
        
        try:
            request_extra_body = dict(extra_body) if extra_body else {}
            request_extra_body["structured_outputs"] = {"json": MODEL_PROVENANCE_GUIDED_JSON_SCHEMA}
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_completion_tokens=max_completion_tokens,
                extra_body=request_extra_body
            )
            
            trace["response"] = response.model_dump()
            
            content = response.choices[0].message.content or ""
            parsed = json.loads(content)
            
            return parsed, trace
            
        except Exception as e:
            self.logger.error(f"Error extracting provenance for article {article_id}: {e}")
            trace["error"] = str(e)
            return None, trace
