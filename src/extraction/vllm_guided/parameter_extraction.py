# src/extraction/vllm_guided/parameter_extraction.py
"""
vLLM Guided JSON extraction for parameters.

This module provides guided JSON decoding for parameter extraction,
ensuring strict schema compliance.
"""

import datetime as dt
import json
import logging
import os
import uuid
from json.decoder import JSONDecodeError
from pathlib import Path
from threading import Lock
from typing import Callable, Dict, Optional

import pandas as pd
from openai import OpenAI
from tqdm import tqdm

from src.extraction.common import (
    apply_extraction_sample,
    append_jsonl,
    get_data_extraction_concurrency,
    load_extraction_input_dataframe,
    run_with_optional_thread_pool,
)
from ..parameters.extraction_responses_api.tools import (
    AttackRateExtractor, GrowthRateExtractor, HumanDelayExtractor,
    MutationRateExtractor, RelativeContributionExtractor,
    ReproductionNumberExtractor, SeroprevalenceExtractor, SeverityExtractor
)
from ..parameters.extraction_responses_api.tools.extractor import (
    ParameterExtractionResult, ParameterExtractor
)
from utils.screening_prompts import get_study_objectives
from utils.schemas import PARAMETER_CLASSES_MAPPING, VALID_PATHOGENS

from .parameter_schemas import (
    SCREENING_GUIDED_JSON_SCHEMA,
    UNCERTAINTY_GUIDED_JSON_SCHEMA,
    POPULATION_GUIDED_JSON_SCHEMA,
    AGGREGATION_GUIDED_JSON_SCHEMA,
    PARAMETER_VALUE_SCHEMAS,
)

PARAMETER_RESPONSES_API_DIR = (
    Path(__file__).resolve().parent.parent / "parameters" / "extraction_responses_api"
)
PARAMETER_PROMPTS_DIR = PARAMETER_RESPONSES_API_DIR / "prompts"
PARAMETER_TOOLS_DIR = PARAMETER_RESPONSES_API_DIR / "tools"


class GuidedParameterExtractionRunner:
    """
    Parameter extraction runner using vLLM guided JSON decoding.
    """

    EXTRACTORS: Dict[str, type[ParameterExtractor]] = {
        "attack_rate": AttackRateExtractor,
        "growth_rate": GrowthRateExtractor,
        "human_delay": HumanDelayExtractor,
        "mutation_rate": MutationRateExtractor,
        "relative_contribution": RelativeContributionExtractor,
        "reproduction_number": ReproductionNumberExtractor,
        "seroprevalence": SeroprevalenceExtractor,
        "severity": SeverityExtractor,
    }

    def __init__(
        self,
        client: OpenAI,
        run_id: str,
        model_name: str,
        pathogen: str,
        parameter_classes: list[str],
        fulltext: pd.DataFrame,
        log_dir: Optional[str] = None,
        output_parameters_file: Optional[str] = None,
        max_completion_tokens: int = 98304,
        article_concurrency: int = 1,
    ):
        self.client = client
        self.run_id = run_id
        self.model_name = model_name
        self.pathogen = pathogen
        self.parameter_classes = parameter_classes
        self.fulltext = fulltext
        self.output_parameters_file = output_parameters_file
        self.max_completion_tokens = max_completion_tokens
        self.article_concurrency = max(1, int(article_concurrency))
        self._append_lock = Lock()

        self.extra_body = {"thinking": {"type": "enabled"}} if 'gpt' not in self.model_name.lower() else None

        self.system_prompt = self._read_text(
            PARAMETER_PROMPTS_DIR / "basic_instruction.md"
        )
        self.system_prompt += "\n" + get_study_objectives(pathogen)

        self.start_time = dt.datetime.now()

        if log_dir is None:
            self.log_dir = (
                "logs/"
                f"{self.start_time.strftime('%Y-%m-%d_%H-%M-%S')}_{run_id}/{pathogen}"
            )
        else:
            self.log_dir = str(log_dir)

        self.traces_dir = os.path.join(self.log_dir, "traces")
        self.results_dir = os.path.join(self.log_dir, "results")

        self.logger = self._init_logger()

    def _init_logger(self) -> logging.Logger:
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.traces_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)

        logger = logging.getLogger(f"parameter_extraction_guided_{self.run_id}")
        logger.setLevel(logging.INFO)

        if logger.handlers:
            logger.handlers.clear()

        fh = logging.FileHandler(f"{self.log_dir}/extraction.log")
        fh.setLevel(logging.INFO)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

        return logger

    def _append_jsonl(self, path: str, obj: dict):
        append_jsonl(path, obj, lock=self._append_lock)

    @staticmethod
    def _read_text(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _save_trace(self, article_id: str, stage: str, trace: dict):
        trace_path = os.path.join(self.traces_dir, f"{article_id}_{stage}_trace.json")
        with open(trace_path, "w") as f:
            json.dump(trace, f, indent=2)
        self._append_jsonl(os.path.join(self.log_dir, "reasoning_traces.jsonl"), trace)

    def _convert_null_values(self, data: dict) -> dict:
        """Convert guided JSON nullables to Python None.
        
        Note: We must check `v is False` explicitly because `False == 0` in Python,
        which would incorrectly convert boolean False to None.
        """
        result = {}
        for k, v in data.items():
            # Preserve boolean False (don't convert to None)
            if v is False:
                result[k] = False
            elif v == "null" or v == "" or v == 0:
                result[k] = None
            else:
                result[k] = v
        return result

    def _convert_screening_args(self, data: dict) -> dict:
        """Extract only expected screening fields."""
        return {
            "contains_parameter": data.get("contains_parameter", False),
            "annotations": data.get("annotations") if data.get("annotations") not in ["", "null"] else None,
        }

    def _convert_uncertainty_args(self, data: dict) -> dict:
        """Extract only expected uncertainty fields, ignoring any extras."""
        def nullable_str(val):
            return None if val in ["null", "", None] else val
        def nullable_num(val):
            return None if val in [0, None, "null"] else val
        
        return {
            "value_type": data.get("value_type"),
            "statistical_approach": data.get("statistical_approach"),
            "single_type_uncertainty": nullable_str(data.get("single_type_uncertainty")),
            "single_type_uncertainty_value": nullable_num(data.get("single_type_uncertainty_value")),
            "paired_uncertainty": nullable_str(data.get("paired_uncertainty")),
            "paired_uncertainty_lower_bound": nullable_num(data.get("paired_uncertainty_lower_bound")),
            "paired_uncertainty_upper_bound": nullable_num(data.get("paired_uncertainty_upper_bound")),
            "distribution_type": nullable_str(data.get("distribution_type")),
        }

    def _convert_population_args(self, data: dict) -> dict:
        """Extract only expected population fields, ignoring any extras."""
        def nullable_str(val):
            return None if val in ["null", "", None] else val
        def nullable_int(val):
            return None if val in [0, None, "null"] else val
        
        return {
            "population_sex": data.get("population_sex"),
            "population_sample_type": data.get("population_sample_type"),
            "population_group": data.get("population_group"),
            "population_sample_size": nullable_int(data.get("population_sample_size")),
            "population_age_min": nullable_int(data.get("population_age_min")),
            "population_age_max": nullable_int(data.get("population_age_max")),
            "population_country": nullable_str(data.get("population_country")),
            "population_location": nullable_str(data.get("population_location")),
        }

    def _convert_aggregation_args(self, data: dict) -> dict:
        """Extract only expected aggregation fields, ignoring any extras.
        
        Raises ValueError if required fields are missing/None.
        """
        lb = data.get("lower_bound")
        ub = data.get("upper_bound")
        
        # Validate required fields are present
        if lb is None or ub is None:
            raise ValueError(
                f"Missing required aggregation fields. Got lower_bound={lb}, upper_bound={ub}. "
                f"Raw data keys: {list(data.keys())}"
            )
        
        return {
            "lower_bound": lb,
            "upper_bound": ub,
            "disaggregated_by": data.get("disaggregated_by", []),
            "aggregated_ids": data.get("aggregated_ids", []),
        }

    def _convert_value_args(self, parameter: str, data: dict) -> dict:
        """Extract only expected value extraction fields based on parameter type.
        
        Raises ValueError if required fields are missing.
        """
        def nullable_str(val):
            return None if val in ["null", "", None] else val
        def nullable_int(val):
            return None if val in [0, None, "null"] else val
        
        # All parameter types require 'value'
        if data.get("value") is None:
            raise ValueError(f"Missing required field 'value'. Raw data: {data}")
        
        if parameter == "reproduction_number":
            return {
                "value": data.get("value"),
                "type": data.get("type"),
                "transmission": data.get("transmission"),
                "method": data.get("method"),
            }
        elif parameter == "attack_rate":
            return {
                "value": data.get("value"),
                "unit": data.get("unit"),
                "rate_denominator": nullable_int(data.get("rate_denominator")),
            }
        elif parameter == "growth_rate":
            return {
                "value": data.get("value"),
                "unit": data.get("unit"),
            }
        elif parameter == "human_delay":
            return {
                "value": data.get("value"),
                "delay_type": data.get("delay_type"),
                "unit": data.get("unit"),
                "delay_type_note": nullable_str(data.get("delay_type_note")),
            }
        elif parameter == "mutation_rate":
            return {
                "value": data.get("value"),
                "parameter_type": data.get("parameter_type"),
                "unit": data.get("unit"),
                "genome_site": data.get("genome_site"),
            }
        elif parameter == "relative_contribution":
            return {
                "value": data.get("value"),
                "type": data.get("type"),
            }
        elif parameter == "seroprevalence":
            return {
                "value": data.get("value"),
                "parameter_type": data.get("parameter_type"),
                "numerator": nullable_int(data.get("numerator")),
                "denominator": nullable_int(data.get("denominator")),
            }
        elif parameter == "severity":
            return {
                "value": data.get("value"),
                "numerator": nullable_int(data.get("numerator")),
                "denominator": nullable_int(data.get("denominator")),
                "parameter_type": data.get("parameter_type"),
                "method": nullable_str(data.get("method")),
                "value_type": data.get("value_type"),
                "statistical_approach": data.get("statistical_approach"),
            }
        else:
            # Fallback - return data as-is
            return self._convert_null_values(data)

    def _guided_extraction(
        self,
        schema: dict,
        system_prompt: str,
        user_prompt: str,
        article_id: str,
        stage: str,
        extractor_fn: Optional[Callable] = None,
        parameter: str = "",
        multi_extract: bool = False,
        converter_fn: Optional[Callable] = None,
    ) -> tuple[list[dict], dict]:
        """
        Generic guided extraction with a schema.
        
        Follows the exact same pattern as model_extraction.py for consistency.
        
        Args:
            schema: JSON schema for guided decoding
            system_prompt: System prompt
            user_prompt: User prompt with article text
            article_id: Article identifier
            stage: Stage name for logging
            extractor_fn: Optional validation function
            parameter: Parameter class name
            multi_extract: If True, extract multiple items until "done"
            converter_fn: Optional function to convert raw JSON to expected args
                         (filters out extra fields the model may add)
        
        Returns:
            Tuple of (list of extractions, trace dict)
        """
        # Build guided-specific prompt - exactly like model_extraction.py
        if multi_extract:
            guided_instructions = """

IMPORTANT: Analyze the article carefully. Your final response must be a JSON object.

For each parameter found, output:
{"action": "extract", "data": {...}}

When you have extracted ALL parameters and there are no more to extract, output:
{"action": "done"}

Extract one parameter at a time. After each extraction, I will ask you to continue."""
        else:
            guided_instructions = """

IMPORTANT: Your final response must be a JSON object matching the required schema.
Output only valid JSON, no other text."""

        # Combine system prompt with guided instructions (like model_extraction.py)
        full_system_prompt = system_prompt + "\n\n" + guided_instructions

        input_list = [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        trace = {
            "stage": stage,
            "article_id": article_id,
            "parameter": parameter,
            "timestamp": dt.datetime.now().isoformat(),
            "input": input_list.copy(),
            "iterations": [],
            "extractions": [],
            "error": None,
        }

        extractions = []
        max_iterations = 50  # Same as model_extraction.py
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
                request_extra_body = dict(self.extra_body) if self.extra_body else {}
                request_extra_body["structured_outputs"] = {"json": schema}

                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=input_list,
                    reasoning_effort="high",
                    max_completion_tokens=self.max_completion_tokens,
                    extra_body=request_extra_body,
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

                # Handle empty response
                if not content or content.strip() == "":
                    self.logger.warning(f"Empty response for {article_id} {stage}, retrying...")
                    if multi_extract:
                        input_list.append({
                            "role": "user",
                            "content": 'Your response was empty. Please respond with valid JSON: either {"action": "extract", "data": {...}} or {"action": "done"}'
                        })
                    else:
                        input_list.append({
                            "role": "user",
                            "content": "Your response was empty. Please respond with valid JSON matching the schema."
                        })
                    trace["iterations"].append(iteration_trace)
                    continue

                # Strip markdown code fences if present (model sometimes wraps JSON in ```json ... ```)
                json_content = content.strip()
                if json_content.startswith("```"):
                    # Remove opening fence (```json or ```)
                    lines = json_content.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    # Remove closing fence
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    json_content = "\n".join(lines).strip()

                # Parse JSON from response - with structured_outputs, content should be pure JSON
                try:
                    parsed = json.loads(json_content)
                    iteration_trace["parsed_json"] = parsed
                except JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSON for article {article_id}: {e}")
                    self.logger.warning(f"Raw content (first 200 chars): '{content[:200]}'")
                    # Ask for retry - same message format as model_extraction.py
                    if multi_extract:
                        input_list.append({
                            "role": "user",
                            "content": 'Invalid JSON. Please respond with RAW JSON only, no markdown code fences. Either {"action": "extract", "data": {...}} or {"action": "done"}'
                        })
                    else:
                        input_list.append({
                            "role": "user",
                            "content": "Invalid JSON. Please respond with RAW JSON only, no markdown code fences."
                        })
                    trace["iterations"].append(iteration_trace)
                    continue

                # For multi-extract mode
                if multi_extract:
                    # Check if done
                    action = parsed.get("action", "")
                    if action == "done":
                        self.logger.info(f"Extraction complete for {article_id} {stage}, found {len(extractions)} items")
                        trace["iterations"].append(iteration_trace)
                        break

                    if action != "extract" or "data" not in parsed:
                        input_list.append({
                            "role": "user",
                            "content": 'Please extract the next parameter or indicate you are done with {"action": "done"}'
                        })
                        trace["iterations"].append(iteration_trace)
                        continue

                    # Convert and validate - use converter if provided to filter extra fields
                    raw_data = parsed["data"]
                    if converter_fn:
                        data = converter_fn(raw_data)
                    else:
                        data = self._convert_null_values(raw_data)
                    
                    if extractor_fn:
                        try:
                            result = extractor_fn(parameter=parameter, **data)
                        except Exception as e:
                            self.logger.error(f"Validation error for {article_id}: {e}")
                            result = ParameterExtractionResult(
                                parameter=parameter,
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
                                "id": str(uuid.uuid4()),
                                **result.content
                            }
                            extractions.append(extraction_data)
                            trace["extractions"].append(extraction_data)
                            
                            # Ask for next - same pattern as model_extraction.py
                            input_list.append({
                                "role": "user",
                                "content": "Extracted successfully. Are there any more parameters to extract? If yes, extract the next one. If no, respond with {\"action\": \"done\"}"
                            })
                        else:
                            self.logger.warning(f"Validation failed for {article_id}: {result.message}")
                            # Ask to re-extract with corrections
                            input_list.append({
                                "role": "user",
                                "content": f"Validation failed: {result.message}. Please re-extract with corrections."
                            })
                    else:
                        extractions.append(data)
                        trace["extractions"].append(data)
                        input_list.append({
                            "role": "user",
                            "content": "Extracted. Continue or output {\"action\": \"done\"}"
                        })

                else:
                    # Single extraction mode (for uncertainty, population, etc.)
                    # Use converter if provided to filter extra fields
                    if converter_fn:
                        data = converter_fn(parsed)
                    else:
                        data = self._convert_null_values(parsed)
                    
                    if extractor_fn:
                        try:
                            result = extractor_fn(parameter=parameter, **data)
                        except Exception as e:
                            self.logger.error(f"Validation error for {article_id}: {e}")
                            result = ParameterExtractionResult(
                                parameter=parameter,
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
                            extractions.append(result.content)
                            trace["extractions"].append(result.content)
                            trace["iterations"].append(iteration_trace)
                            break
                        else:
                            self.logger.warning(f"Validation failed for {article_id}: {result.message}")
                            input_list.append({
                                "role": "user",
                                "content": f"Validation failed: {result.message}. Please re-extract with corrections."
                            })
                    else:
                        extractions.append(data)
                        trace["extractions"].append(data)
                        trace["iterations"].append(iteration_trace)
                        break

                trace["iterations"].append(iteration_trace)

            except Exception as e:
                self.logger.error(f"Error during extraction for {article_id}: {e}")
                iteration_trace["error"] = str(e)
                trace["iterations"].append(iteration_trace)
                trace["error"] = str(e)
                break

        trace["extractions"] = extractions
        return extractions, trace

    def screen_parameters(self, user_prompt: str, row: pd.Series) -> dict[str, bool]:
        """Screen article for each parameter class."""
        screening_results = {}
        article_id = str(row["article_id"])
        screening_prompt = self.system_prompt + "\n" + self._read_text(
            PARAMETER_PROMPTS_DIR / "screening.md"
        )

        for parameter_class in self.parameter_classes:
            parameter_screening_prompt = screening_prompt + "\n" + self._read_text(
                PARAMETER_TOOLS_DIR / parameter_class / "screening.md"
            )

            parameter_screening_prompt += "\n\nRespond with JSON: {\"contains_parameter\": true/false, \"annotations\": \"excerpt or empty string\"}"

            extractions, trace = self._guided_extraction(
                schema=SCREENING_GUIDED_JSON_SCHEMA,
                system_prompt=parameter_screening_prompt,
                user_prompt=user_prompt,
                article_id=article_id,
                stage=f"screening_{parameter_class}",
                parameter=parameter_class,
                multi_extract=False,
                converter_fn=self._convert_screening_args,
            )

            contains_parameter = False
            annotations = None
            if extractions:
                contains_parameter = extractions[0].get("contains_parameter", False)
                annotations = extractions[0].get("annotations")
                if annotations == "":
                    annotations = None

            screening_results[parameter_class] = contains_parameter

            self._append_jsonl(
                os.path.join(self.results_dir, "screening.jsonl"),
                {
                    "article_id": article_id,
                    "parameter_class": parameter_class,
                    "contains_parameter": contains_parameter,
                    "annotations": annotations,
                    "timestamp": dt.datetime.now().isoformat()
                }
            )

            self._save_trace(article_id, f"screening_{parameter_class}", trace)

        total_positive = sum(screening_results.values())
        self.logger.info(
            f"Screening complete for article {article_id}: "
            f"{total_positive}/{len(self.parameter_classes)} parameter classes contain data"
        )

        return screening_results

    def extract_single_paper_parameters(self, row: pd.Series):
        """Extract all parameters from a single paper."""
        user_prompt = (
            f"# Article title: {row['title']}\n"
            f"# Full Text\n"
            f"{row['markdown_content']}"
        )

        article_id = str(row["article_id"])

        screening_results = self.screen_parameters(user_prompt, row)

        for parameter, contains_parameter in screening_results.items():
            if not contains_parameter:
                self.logger.info(
                    f"Parameter {parameter} did not pass screening for "
                    f"article_id {article_id}. Skipping extraction."
                )
                continue

            if parameter not in self.EXTRACTORS:
                self.logger.info(
                    f"No extractor implemented for parameter type {parameter}. "
                    "Skipping extraction."
                )
                continue

            if parameter not in PARAMETER_VALUE_SCHEMAS:
                self.logger.info(
                    f"No guided schema for parameter type {parameter}. "
                    "Skipping extraction."
                )
                continue

            extractor = self.EXTRACTORS[parameter]()

            # Value extraction
            extraction_prompt = self.system_prompt + "\n" + self._read_text(
                PARAMETER_PROMPTS_DIR / "value_extraction.md"
            )
            extraction_prompt += "\n" + self._read_text(
                PARAMETER_TOOLS_DIR / parameter / "value_extraction.md"
            )

            extracted_parameters, extraction_trace = self._guided_extraction(
                schema=PARAMETER_VALUE_SCHEMAS[parameter],
                system_prompt=extraction_prompt,
                user_prompt=user_prompt,
                article_id=article_id,
                stage=f"value_extraction_{parameter}",
                extractor_fn=extractor.extract_value,
                parameter=parameter,
                multi_extract=True,
                converter_fn=lambda d, p=parameter: self._convert_value_args(p, d),
            )

            self._append_jsonl(
                os.path.join(self.results_dir, "values.jsonl"),
                {
                    "article_id": article_id,
                    "our_screening_decision": row.get("our_screening_decision", None),
                    "parameter_class": parameter,
                    "extraction": extracted_parameters,
                    "timestamp": dt.datetime.now().isoformat()
                }
            )

            self.logger.info(
                f"Successfully extracted {len(extracted_parameters)} value(s) "
                f"for {parameter} from article {article_id}"
            )

            self._save_trace(article_id, f"values_{parameter}", extraction_trace)

            if len(extracted_parameters) == 0:
                continue

            # Uncertainty extraction
            uncertainty_prompt = self.system_prompt + "\n" + self._read_text(
                PARAMETER_PROMPTS_DIR / "uncertainty.md"
            )

            extracted_with_uncertainty = []

            for idx, extracted_param in enumerate(extracted_parameters):
                uncertainty_user_prompt = user_prompt + f"\n\n# Extracted parameter:\n{json.dumps(extracted_param)}"

                uncertainty_extractions, uncertainty_trace = self._guided_extraction(
                    schema=UNCERTAINTY_GUIDED_JSON_SCHEMA,
                    system_prompt=uncertainty_prompt,
                    user_prompt=uncertainty_user_prompt,
                    article_id=article_id,
                    stage=f"uncertainty_{parameter}_{idx}",
                    extractor_fn=extractor.extract_uncertainty_info,
                    parameter=f"{parameter} uncertainty",
                    multi_extract=False,
                    converter_fn=self._convert_uncertainty_args,
                )

                if uncertainty_extractions:
                    combined = {**extracted_param, **uncertainty_extractions[0]}
                    extracted_with_uncertainty.append(combined)

                    self._append_jsonl(
                        os.path.join(self.results_dir, "uncertainties.jsonl"),
                        {
                            "article_id": article_id,
                            "parameter_class": parameter,
                            "extraction": combined,
                            "timestamp": dt.datetime.now().isoformat()
                        }
                    )

                self._save_trace(article_id, f"uncertainty_{parameter}_{idx}", uncertainty_trace)

            # Population extraction
            population_prompt = self.system_prompt + "\n" + self._read_text(
                PARAMETER_PROMPTS_DIR / "population.md"
            )

            extracted_with_population = []

            for idx, extracted_param in enumerate(extracted_with_uncertainty):
                population_user_prompt = user_prompt + f"\n\n# Extracted parameter:\n{json.dumps(extracted_param)}"

                population_extractions, population_trace = self._guided_extraction(
                    schema=POPULATION_GUIDED_JSON_SCHEMA,
                    system_prompt=population_prompt,
                    user_prompt=population_user_prompt,
                    article_id=article_id,
                    stage=f"population_{parameter}_{idx}",
                    extractor_fn=extractor.extract_population_info,
                    parameter=f"{parameter} population",
                    multi_extract=False,
                    converter_fn=self._convert_population_args,
                )

                if population_extractions:
                    combined = {**extracted_param, **population_extractions[0]}
                    extracted_with_population.append(combined)

                    self._append_jsonl(
                        os.path.join(self.results_dir, "populations.jsonl"),
                        {
                            "article_id": article_id,
                            "parameter_class": parameter,
                            "extraction": combined,
                            "timestamp": dt.datetime.now().isoformat()
                        }
                    )

                    self._append_jsonl(
                        os.path.join(self.results_dir, "raw_parameters.jsonl"),
                        {
                            "article_id": article_id,
                            "our_screening_decision": row.get("our_screening_decision", None),
                            "parameter_class": parameter,
                            "extraction": combined,
                            "aggregated": False,
                            "timestamp": dt.datetime.now().isoformat()
                        }
                    )

                self._save_trace(article_id, f"population_{parameter}_{idx}", population_trace)

            # Aggregation (if multiple parameters)
            if len(extracted_with_population) > 1:
                self.logger.info(
                    "There are multiple extracted parameters. Attempting aggregation..."
                )

                aggregation_prompt = self.system_prompt + "\n" + self._read_text(
                    PARAMETER_PROMPTS_DIR / "aggregation.md"
                )

                aggregation_user_prompt = user_prompt + f"\n\n# Extracted parameters:\n{json.dumps(extracted_with_population)}"

                aggregated_params, aggregation_trace = self._guided_extraction(
                    schema=AGGREGATION_GUIDED_JSON_SCHEMA,
                    system_prompt=aggregation_prompt,
                    user_prompt=aggregation_user_prompt,
                    article_id=article_id,
                    stage=f"aggregation_{parameter}",
                    extractor_fn=extractor.extract_aggregated_parameters,
                    parameter=f"{parameter} aggregation",
                    multi_extract=False,
                    converter_fn=self._convert_aggregation_args,
                )

                for result in aggregated_params:
                    result["id"] = str(uuid.uuid4())
                    
                    self._append_jsonl(
                        os.path.join(self.results_dir, "aggregations.jsonl"),
                        {
                            "article_id": article_id,
                            "parameter_class": parameter,
                            "extraction": result,
                            "timestamp": dt.datetime.now().isoformat()
                        }
                    )

                    self._append_jsonl(
                        os.path.join(self.results_dir, "raw_parameters.jsonl"),
                        {
                            "article_id": article_id,
                            "our_screening_decision": row.get("our_screening_decision", None),
                            "parameter_class": parameter,
                            "extraction": result,
                            "aggregated": True,
                            "timestamp": dt.datetime.now().isoformat()
                        }
                    )

                self._save_trace(article_id, f"aggregation_{parameter}", aggregation_trace)

    def write_final_parameters(self):
        """Write final parameters after filtering aggregated ones."""
        raw_path = os.path.join(self.log_dir, "results", "raw_parameters.jsonl")
        
        if not os.path.exists(raw_path):
            self.logger.warning("No raw_parameters.jsonl found")
            return

        with open(raw_path, "r") as f:
            raw_parameters = [json.loads(line) for line in f]

        uuids_in_aggregations = set()
        for entry in raw_parameters:
            if entry.get("aggregated", False):
                uuids_in_aggregations.update(
                    entry["extraction"].get("aggregated_ids", [])
                )

        final_parameters = [
            entry for entry in raw_parameters
            if entry["extraction"].get("id") not in uuids_in_aggregations
        ]

        with open(os.path.join(self.log_dir, "results", "final_parameters.jsonl"), "w") as f:
            for entry in final_parameters:
                f.write(json.dumps(entry) + "\n")

        output_path = self.output_parameters_file
        if output_path is None:
            output_path = os.path.join(self.log_dir, "extracted_parameters.jsonl")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            for entry in final_parameters:
                f.write(json.dumps(entry) + "\n")

        self.logger.info(f"Saved final parameters to {output_path}")

    def _process_article(self, item: tuple[int, pd.Series]) -> None:
        _, row = item
        self.logger.info(f"PROCESSING ARTICLE ID {row['article_id']}")
        self.extract_single_paper_parameters(row)

    def run(self):
        """Run the extraction pipeline."""
        metadata = {
            "run_id": self.run_id,
            "success": True,
            "start_time": self.start_time.isoformat(),
            "model_name": self.model_name,
            "pathogen": self.pathogen,
            "parameter_classes": self.parameter_classes,
            "num_papers": len(self.fulltext),
            "article_ids": self.fulltext["article_id"].tolist(),
        }
        metadata_path = os.path.join(self.log_dir, "run_metadata.json")

        try:
            rows = list(self.fulltext.iterrows())
            for _ in run_with_optional_thread_pool(
                rows,
                self._process_article,
                self.article_concurrency,
                desc="Processing articles",
            ):
                pass
        except Exception as e:
            self.logger.error(f"Encountered error during extraction run: {e}")
            metadata["success"] = False
            metadata["duration_seconds"] = (
                (dt.datetime.now() - self.start_time).total_seconds()
            )
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=4)

            self.write_final_parameters()
            raise e

        self.write_final_parameters()
        metadata["duration_seconds"] = (
            (dt.datetime.now() - self.start_time).total_seconds()
        )
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=4)


class ParameterRunner(GuidedParameterExtractionRunner):
    """Standard Runner interface for parameter extraction with guided JSON."""

    def __init__(self, config, logger: Optional[logging.Logger] = None):
        start_time = dt.datetime.now()

        if config.pathogen not in VALID_PATHOGENS:
            raise ValueError(
                f"Invalid pathogen: {config.pathogen}. Must be one of {VALID_PATHOGENS}"
            )

        if len(config.parameter_classes) == 1 and config.parameter_classes[0] == "all":
            parameter_classes = list(PARAMETER_CLASSES_MAPPING.values()).copy()
        else:
            parameter_classes = config.parameter_classes
            if any(
                param not in PARAMETER_CLASSES_MAPPING.values()
                for param in parameter_classes
            ):
                raise ValueError(
                    f"Invalid parameter classes: {parameter_classes}. "
                    f"Must be a subset of {PARAMETER_CLASSES_MAPPING.values()}"
                )

        run_id = config.run_id if config.run_id else start_time.strftime("%Y-%m-%d_%H-%M-%S")

        log_dir = Path(config.log_dir) / f"data_extraction_parameters_dumps_{run_id}"
        log_dir.mkdir(parents=True, exist_ok=True)

        if config.base_url is not None:
            client = OpenAI(base_url=config.base_url, api_key=config.api_key)
        else:
            client = OpenAI(api_key=config.api_key)

        fulltext = load_extraction_input_dataframe(config, logger=logger)
        fulltext = apply_extraction_sample(fulltext, config, logger=logger)

        if config.limit is not None:
            fulltext = fulltext.head(config.limit)

        super().__init__(
            client=client,
            run_id=run_id,
            model_name=config.model_name,
            pathogen=config.pathogen,
            parameter_classes=parameter_classes,
            fulltext=fulltext,
            log_dir=str(log_dir),
            output_parameters_file=str(config.data_extraction_parameters_path),
            max_completion_tokens=getattr(config, "max_completion_tokens", 98304),
            article_concurrency=get_data_extraction_concurrency(config),
        )

        if logger is not None:
            for h in list(self.logger.handlers):
                try:
                    logger.addHandler(h)
                except Exception:
                    pass
