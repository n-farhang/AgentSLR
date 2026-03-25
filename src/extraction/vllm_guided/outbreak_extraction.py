# src/extraction/vllm_guided/outbreak_extraction.py
"""
vLLM Guided JSON extraction for outbreaks.

This module provides a wrapper class that can be used with the existing
OutbreakExtractionRunner to extract outbreaks using grammar-constrained decoding
instead of tool calls.
"""

import json
import logging
from json.decoder import JSONDecodeError
from typing import Optional

from openai import OpenAI

from ..outbreaks.extraction.extractor import (
    OutbreakExtractor,
    OutbreakExtractionResult,
    OutbreakProvenanceResult,
)
from .schemas import OUTBREAK_GUIDED_JSON_SCHEMA, OUTBREAK_PROVENANCE_GUIDED_JSON_SCHEMA


class GuidedOutbreakExtractor:
    """
    Extracts outbreak data using vLLM guided JSON decoding.
    
    This class provides an alternative extraction method that uses
    grammar-constrained decoding to ensure strict schema compliance,
    rather than relying on tool/function calls.
    
    Usage:
        guided = GuidedOutbreakExtractor(client, model_name, logger)
        extractions, trace = guided.extract_outbreaks(
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
        self.extractor = OutbreakExtractor()
    
    def _convert_guided_json_to_outbreak_args(self, data: dict) -> dict:
        """Convert guided JSON response to function arguments format.
        
        The guided JSON schema uses:
        - Integers for numeric fields (use 0 for null)
        - "null" string in enums for nullable string fields
        - Native booleans
        """
        outbreak_data = data.get("outbreak_data", data)
        
        # Convert 0 to None for nullable integer fields
        def nullable_int(val):
            if val == 0 or val is None:
                return None
            return val
        
        # Convert "null" or empty string to None for nullable string fields
        def nullable_str(val):
            if val == "null" or val == "" or val is None:
                return None
            return val
        
        # Convert 0 to None for nullable number fields
        def nullable_num(val):
            if val == 0 or val is None:
                return None
            return val
        
        return {
            "outbreak_start_day": nullable_int(outbreak_data.get("outbreak_start_day")),
            "outbreak_start_month": nullable_str(outbreak_data.get("outbreak_start_month")),
            "outbreak_start_year": nullable_int(outbreak_data.get("outbreak_start_year")),
            "outbreak_end_day": nullable_int(outbreak_data.get("outbreak_end_day")),
            "outbreak_end_month": nullable_str(outbreak_data.get("outbreak_end_month")),
            "outbreak_end_year": nullable_int(outbreak_data.get("outbreak_end_year")),
            "outbreak_duration_months": nullable_num(outbreak_data.get("outbreak_duration_months")),
            "outbreak_is_currently_ongoing": outbreak_data.get("outbreak_is_currently_ongoing"),
            "outbreak_country": outbreak_data.get("outbreak_country"),
            "outbreak_location": nullable_str(outbreak_data.get("outbreak_location")),
            "outbreak_location_type": nullable_str(outbreak_data.get("outbreak_location_type")),
            "outbreak_source": nullable_str(outbreak_data.get("outbreak_source")),
            "mode_of_detection": nullable_str(outbreak_data.get("mode_of_detection")),
            "method_of_case_definition": nullable_str(outbreak_data.get("method_of_case_definition")),
            "pre_outbreak": nullable_str(outbreak_data.get("pre_outbreak")),
            "cases_confirmed": nullable_int(outbreak_data.get("cases_confirmed")),
            "cases_probable": nullable_int(outbreak_data.get("cases_probable")),
            "cases_suspected": nullable_int(outbreak_data.get("cases_suspected")),
            "cases_unspecified": nullable_int(outbreak_data.get("cases_unspecified")),
            "cases_asymptomatic": nullable_int(outbreak_data.get("cases_asymptomatic")),
            "cases_severe": nullable_int(outbreak_data.get("cases_severe")),
            "deaths": nullable_int(outbreak_data.get("deaths")),
            "asymptomatic_transmission_described": outbreak_data.get("asymptomatic_transmission_described"),
            "population_size_geographical_area": nullable_int(outbreak_data.get("population_size_geographical_area")),
            "type_cases_sex_disagg": nullable_str(outbreak_data.get("type_cases_sex_disagg")),
            "male_cases": nullable_int(outbreak_data.get("male_cases")),
            "prop_male_cases": nullable_num(outbreak_data.get("prop_male_cases")),
            "female_cases": nullable_int(outbreak_data.get("female_cases")),
            "prop_female_cases": nullable_num(outbreak_data.get("prop_female_cases")),
            "notes": nullable_str(outbreak_data.get("notes")),
        }
    
    def extract_outbreaks(
        self,
        article_text: str,
        article_id: str,
        system_prompt: str,
        extraction_prompt: str,
        max_completion_tokens: int = 98304,
        extra_body: Optional[dict] = None,
    ) -> tuple[list[dict], dict]:
        """
        Extract outbreaks using vLLM guided JSON decoding.
        
        Args:
            article_text: Full text of the article
            article_id: Article identifier for logging
            system_prompt: System prompt for the LLM
            extraction_prompt: Extraction instructions prompt
            max_completion_tokens: Max tokens for completion
            extra_body: Additional body params (e.g., thinking mode)
            
        Returns:
            Tuple of (list of extracted outbreak dicts, trace dict)
        """
        import datetime as dt
        
        # Build guided-specific prompt
        guided_prompt = extraction_prompt + """

IMPORTANT: Analyze the article carefully. Your final response must be a JSON object.

For each outbreak found, output:
{"action": "extract_outbreak", "outbreak_data": {...}}

When you have extracted ALL outbreaks and there are no more to extract, output:
{"action": "done"}

Extract one outbreak at a time. After each extraction, I will ask you to continue.
Use 0 for integer fields when the value is not available/null."""

        prompt = system_prompt + "\n\n" + guided_prompt

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": article_text},
        ]

        trace = {
            "stage": "extraction_guided",
            "article_id": article_id,
            "timestamp": dt.datetime.now().isoformat(),
            "input": messages.copy(),
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
                request_extra_body["structured_outputs"] = {"json": OUTBREAK_GUIDED_JSON_SCHEMA}

                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    reasoning_effort="high",
                    max_completion_tokens=max_completion_tokens,
                    extra_body=request_extra_body
                )

                iteration_trace["response"] = response.model_dump()

                message = response.choices[0].message
                content = message.content or ""
                
                # Capture reasoning content if present
                reasoning_content = getattr(message, 'reasoning_content', None)
                if reasoning_content:
                    iteration_trace["reasoning"] = reasoning_content
                
                messages.append({"role": "assistant", "content": content})

                # Parse JSON from response
                try:
                    parsed = json.loads(content)
                    iteration_trace["parsed_json"] = parsed
                except JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSON for article {article_id}: {e}")
                    self.logger.debug(f"Raw content: {content[:500]}")
                    messages.append({
                        "role": "user",
                        "content": "Invalid JSON. Please respond with valid JSON."
                    })
                    trace["iterations"].append(iteration_trace)
                    continue

                action = parsed.get("action", "")
                if action == "done":
                    self.logger.info(f"Outbreak extraction complete for article {article_id}, found {len(extractions)} outbreaks")
                    trace["iterations"].append(iteration_trace)
                    break

                if action != "extract_outbreak" or "outbreak_data" not in parsed:
                    messages.append({
                        "role": "user",
                        "content": 'Please extract the next outbreak or indicate you are done with {"action": "done"}'
                    })
                    trace["iterations"].append(iteration_trace)
                    continue

                function_args = self._convert_guided_json_to_outbreak_args(parsed)
                
                try:
                    result = self.extractor.validate_outbreak(**function_args)
                except Exception as e:
                    self.logger.error(f"Validation error for article {article_id}: {e}")
                    result = OutbreakExtractionResult(
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
                    
                    # Ask for next outbreak
                    messages.append({
                        "role": "user",
                        "content": 'Outbreak extracted successfully. Are there any more outbreaks to extract? If yes, extract the next one. If no, respond with {"action": "done"}'
                    })
                else:
                    self.logger.warning(f"Validation failed for outbreak in article {article_id}: {result.message}")
                    # Ask to re-extract with corrections
                    messages.append({
                        "role": "user",
                        "content": f"Validation failed: {result.message}. Please re-extract with corrections."
                    })

                trace["iterations"].append(iteration_trace)

            except Exception as e:
                self.logger.error(f"Error during outbreak extraction for article {article_id}: {e}")
                iteration_trace["error"] = str(e)
                trace["iterations"].append(iteration_trace)
                trace["error"] = str(e)
                break

        return extractions, trace
    
    def extract_provenance(
        self,
        article_text: str,
        article_id: str,
        outbreak_data: dict,
        system_prompt: str,
        max_completion_tokens: int = 98304,
        extra_body: Optional[dict] = None,
    ) -> tuple[Optional[dict], dict]:
        """
        Extract provenance (excerpts) for an outbreak using guided JSON.
        
        Args:
            article_text: Full text of the article
            article_id: Article identifier
            outbreak_data: The extracted outbreak data to get provenance for
            system_prompt: System prompt
            max_completion_tokens: Max tokens
            extra_body: Additional body params
            
        Returns:
            Tuple of (provenance dict or None, trace dict)
        """
        import datetime as dt
        
        provenance_prompt = f"""Extract direct quotes from the article that support the following outbreak extraction:

{json.dumps(outbreak_data, indent=2)}

Provide exact quotes from the article text that justify each extracted value."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": article_text},
            {"role": "assistant", "content": f"I have extracted this outbreak data: {json.dumps(outbreak_data)}"},
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
            request_extra_body["structured_outputs"] = {"json": OUTBREAK_PROVENANCE_GUIDED_JSON_SCHEMA}
            
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
