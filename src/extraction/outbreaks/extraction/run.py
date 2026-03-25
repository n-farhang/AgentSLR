# src/extraction/outbreaks/extraction/run.py
import datetime as dt
import json
import logging
import os
from argparse import ArgumentParser
from json.decoder import JSONDecodeError
from pathlib import Path
from threading import Lock
from typing import Optional

import pandas as pd
from openai import OpenAI
from tqdm import tqdm

from src.extraction.common import (
    apply_extraction_sample,
    append_jsonl,
    get_data_extraction_concurrency,
    get_chat_reasoning_kwargs,
    prepare_article_fulltext_dataframe,
    run_with_optional_thread_pool,
)
from .extractor import OutbreakExtractor, OutbreakExtractionResult, OutbreakProvenanceResult
from .tools import OUTBREAK_TOOL_CALL, PROVENANCE_TOOL_CALL


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("true", "t", "1", "yes", "y"):
        return True
    if v.lower() in ("false", "f", "0", "no", "n"):
        return False
    raise ValueError("Expected a boolean.")


class _CLIConfig:
    def __init__(self, args):
        self.pathogen = args.pathogen
        self.model_name = args.model_name
        self.port = args.port
        self.api_key = args.api_key

        self.log_dir = Path(args.log_dir)

        self.fulltext_screening_path = Path(args.fulltext_screening_path)
        self.data_extraction_outbreaks_path = Path(args.data_extraction_outbreaks_path)

        self.data_value_extraction_enabled_bool = bool(args.data_value_extraction_enabled_bool)
        self.data_extraction_provenance_enabled = bool(args.data_extraction_provenance_enabled)


class OutbreakExtractionRunner:
    
    def __init__(
        self,
        client: OpenAI,
        run_id: str,
        model_name: str,
        pathogen: str,
        fulltext: pd.DataFrame,
        extraction_enabled_bool: bool = True,
        provenance_enabled: bool = True,
        log_dir: Optional[str] = None,
        output_outbreaks_file: Optional[str] = None,
        max_completion_tokens: Optional[int] = None,
        article_concurrency: int = 1,
    ):
        self.client = client
        self.run_id = run_id
        self.model_name = model_name
        self.pathogen = pathogen
        self.fulltext = fulltext
        self.extraction_enabled = extraction_enabled_bool
        self.provenance_enabled = provenance_enabled
        self.output_outbreaks_file = output_outbreaks_file
        self.max_completion_tokens = max_completion_tokens
        self.article_concurrency = max(1, int(article_concurrency))
        self._append_lock = Lock()

        self.extra_body = {"thinking": {"type": "enabled"}} if 'gpt' not in self.model_name.lower() else None

        self.extractor = OutbreakExtractor()
        
        self.start_time = dt.datetime.now()

        if log_dir is None:
            self.log_dir = (
                f"outbreak_extraction/logs/"
                f"{self.start_time.strftime('%Y-%m-%d_%H-%M-%S')}_{run_id}/{self.pathogen}"
            )
        else:
            self.log_dir = str(log_dir)
        
        self.traces_dir = os.path.join(self.log_dir, "traces")
        
        self.logger = self._init_logger()

        self.system_prompt = f"""You are an epidemiologist conducting systematic review of infectious disease outbreaks. Extract structured data about concluded outbreak events from scientific articles.

# Study Objectives
This systematic review collates transmission models, outbreaks and parameters for {self.pathogen}."""

        self.screening_prompt = self._load_prompt("screening")
        self.extraction_prompt = self._load_prompt("extraction")
    
    def _init_logger(self) -> logging.Logger:
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.traces_dir, exist_ok=True)
        
        logger = logging.getLogger(f"outbreak_extraction_{self.run_id}")
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
    
    def _load_prompt(self, prompt_type: str) -> str:
        prompt_path = f"outbreak_extraction/prompts/{prompt_type}.md"
        
        try:
            with open(prompt_path, "r") as f:
                prompt = f.read()
        except FileNotFoundError:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_path = os.path.join(script_dir, "prompts", f"{prompt_type}.md")
            with open(prompt_path, "r") as f:
                prompt = f.read()
        
        return prompt

    def _append_jsonl(self, path: str, obj: dict):
        append_jsonl(path, obj, lock=self._append_lock)
    
    def _save_trace(self, article_id: str, trace: dict):
        trace_path = os.path.join(self.traces_dir, f"{article_id}_trace.json")
        with open(trace_path, "w") as f:
            json.dump(trace, f, indent=2)
        self._append_jsonl(os.path.join(self.log_dir, "reasoning_traces.jsonl"), trace)
    
    def screen_article(self, article_text: str, article_id: str) -> tuple[bool, dict]:
        prompt = self.system_prompt + "\n\n" + self.screening_prompt

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": article_text}
        ]
        
        trace = {
            "stage": "screening",
            "article_id": article_id,
            "timestamp": dt.datetime.now().isoformat(),
            "input": messages.copy(),
            "response": None,
            "decision": None,
            "error": None
        }
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **get_chat_reasoning_kwargs(self.model_name, uses_tools=True),
                max_completion_tokens=self.max_completion_tokens,
                extra_body=self.extra_body if self.extra_body else None
            )
            
            trace["response"] = response.model_dump()
            
            # answer = (response.choices[0].message.content or "").strip()

            content = response.choices[0].message.content
            
            if isinstance(content, list):
                answer = "".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                ).strip()
            else:
                answer = (content or "").strip()

            if answer.lower() == "true":
                answer = "True"
            else:
                answer = "False"
        
            result = answer == "True"
            trace["decision"] = result
            
            self.logger.info(
                f"Screening article {article_id}: {answer}"
            )
            
            log_entry = {
                "article_id": article_id,
                "screening_decision": result,
                "model_response": answer,
                "timestamp": dt.datetime.now().isoformat()
            }
            
            self._append_jsonl(os.path.join(self.log_dir, "screening.jsonl"), log_entry)
            
            self._save_trace(article_id, trace)
            
            return result, trace
            
        except Exception as e:
            self.logger.error(f"Error screening article {article_id}: {e}")
            trace["error"] = str(e)
            self._save_trace(article_id, trace)
            raise RuntimeError(
                f"Outbreak screening failed for article {article_id}: {e}"
            ) from e
    
    def extract_outbreaks(self, article_text: str, article_id: str) -> tuple[list[dict], list[dict], dict]:
        prompt = self.system_prompt + "\n\n" + self.extraction_prompt

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": article_text}
        ]
        
        trace = {
            "stage": "extraction",
            "article_id": article_id,
            "timestamp": dt.datetime.now().isoformat(),
            "input": messages.copy(),
            "iterations": [],
            "extractions": [],
            "error": None
        }
        
        extractions = []
        max_iterations = 50
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            iteration_trace = {
                "iteration": iteration,
                "response": None,
                "tool_calls": []
            }
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=[OUTBREAK_TOOL_CALL],
                    **get_chat_reasoning_kwargs(self.model_name, uses_tools=True),
                    max_completion_tokens=self.max_completion_tokens,
                    extra_body=self.extra_body if self.extra_body else None
                )
                
                iteration_trace["response"] = response.model_dump()
                assistant_msg = response.choices[0].message.model_dump(exclude_none=True)
                messages.append(assistant_msg)

                tool_called = False
                tool_calls = response.choices[0].message.tool_calls or []
                
                for tc in tool_calls:
                    if tc.type != "function":
                        continue
                    
                    if tc.function.name != "extract_outbreak_data":
                        continue
                    
                    tool_called = True
                    call_id = tc.id
                    
                    try:
                        function_args = json.loads(tc.function.arguments)
                    except JSONDecodeError as e:
                        self.logger.error(
                            f"Failed to parse tool arguments for article {article_id}: {e}"
                        )
                        error_message = (
                            f"JSON parsing error: {e}. "
                            f"Could not parse arguments. Please check your JSON formatting."
                        )
                        messages.append({
                             "role": "tool",
                             "tool_call_id": call_id,
                             "content": error_message
                         })
                        
                        iteration_trace["tool_calls"].append({
                            "name": "extract_outbreak_data",
                            "call_id": call_id,
                            "arguments": None,
                            "result": error_message
                        })
                        continue
                    
                    try:
                        result = self.extractor.validate_outbreak(**function_args)
                    except Exception as e:
                        self.logger.error(
                            f"Validation error for article {article_id}: {e}"
                        )
                        result = OutbreakExtractionResult(
                            success=False,
                            message=f"Validation error: {e}",
                            errors=[str(e)],
                            content={}
                        )
                    
                    messages.append({
                         "role": "tool",
                         "tool_call_id": call_id,
                         "content": result.message
                     })
                    
                    iteration_trace["tool_calls"].append({
                        "name": "extract_outbreak_data",
                        "call_id": call_id,
                        "arguments": function_args,
                        "validation_result": {
                            "success": result.success,
                            "message": result.message,
                            "errors": result.errors
                        }
                    })
                    
                    if result.success:
                        result.content["article_id"] = article_id
                        result.content["outbreak_index"] = len(extractions) + 1
                        result.content["extraction_timestamp"] = dt.datetime.now().isoformat()
                        extractions.append(result.content)
                        trace["extractions"].append(result.content)
                        
                        self.logger.info(
                            f"Successfully extracted outbreak {len(extractions)} "
                            f"from article {article_id}"
                        )
                    else:
                        self.logger.warning(
                            f"Validation failed for outbreak in article {article_id}: "
                            f"{result.message}"
                        )
                
                trace["iterations"].append(iteration_trace)
                
                if not tool_called:
                    break
                    
            except Exception as e:
                self.logger.error(f"Error during extraction for article {article_id}: {e}")
                trace["error"] = str(e)
                self._save_trace(article_id, trace)
                raise RuntimeError(
                    f"Outbreak extraction failed for article {article_id}: {e}"
                ) from e
        
        self._save_trace(article_id, trace)
        
        for extraction in extractions:
            self._append_jsonl(os.path.join(self.log_dir, "extractions.jsonl"), extraction)
        
        provenance_rows = []
        if self.provenance_enabled and extractions:
            for idx, extraction in enumerate(extractions):
                provenance, prov_trace = self.extract_provenance(
                    article_text, article_id, extraction, outbreak_index=idx+1
                )
                self._append_jsonl(
                    os.path.join(self.log_dir, "provenance_traces.jsonl"),
                    {
                        "stage": "provenance",
                        "article_id": article_id,
                        "outbreak_index": idx + 1,
                        "timestamp": dt.datetime.now().isoformat(),
                        "trace": prov_trace,
                    },
                )
                if provenance is not None:
                    matching_extraction = next(
                        (
                            o
                            for o in extractions
                            if o.get("article_id") == article_id and o.get("outbreak_index") == (idx + 1)
                        ),
                        extraction,
                    )
                    prov_rows = self._flatten_provenance(article_id, idx + 1, provenance, matching_extraction)
                    provenance_rows.extend(prov_rows)
        
        return extractions, provenance_rows, trace
    
    def extract_provenance(
        self, 
        article_text: str, 
        article_id: str, 
        extracted_values: dict,
        outbreak_index: int = 1
    ) -> tuple[Optional[dict], dict]:
        try:
            with open("outbreak_extraction/prompts/provenance.md", "r") as f:
                provenance_prompt_text = f.read()
        except FileNotFoundError:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            provenance_prompt_path = os.path.join(script_dir, "prompts", "provenance.md")
            with open(provenance_prompt_path, "r") as f:
                provenance_prompt_text = f.read()
        
        prompt = self.system_prompt + "\n\n" + provenance_prompt_text
        
        extracted_summary = f"""# Extracted Outbreak Data (Outbreak {outbreak_index})
                            Country: {extracted_values.get('outbreak_country', 'N/A')}
                            Location: {extracted_values.get('outbreak_location', 'N/A')}
                            Start: {extracted_values.get('outbreak_start_day', '')}/{extracted_values.get('outbreak_start_month', '')}/{extracted_values.get('outbreak_start_year', '')}
                            End: {extracted_values.get('outbreak_end_day', '')}/{extracted_values.get('outbreak_end_month', '')}/{extracted_values.get('outbreak_end_year', '')}
                            Duration (months): {extracted_values.get('outbreak_duration_months', 'N/A')}
                            Source: {extracted_values.get('outbreak_source', 'N/A')}
                            Mode of Detection: {extracted_values.get('mode_of_detection', 'N/A')}
                            Cases Confirmed: {extracted_values.get('cases_confirmed', 'N/A')}
                            Cases Probable: {extracted_values.get('cases_probable', 'N/A')}
                            Cases Suspected: {extracted_values.get('cases_suspected', 'N/A')}
                            Cases Unspecified: {extracted_values.get('cases_unspecified', 'N/A')}
                            Deaths: {extracted_values.get('deaths', 'N/A')}
                            Population Size: {extracted_values.get('population_size_geographical_area', 'N/A')}
                            """
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"{extracted_summary}\n\n# Article Text\n{article_text}"}
        ]
        
        trace = {
            "article_id": article_id,
            "outbreak_index": outbreak_index,
            "timestamp": dt.datetime.now().isoformat(),
            "input": messages.copy(),
            "iterations": [],
            "provenance": None,
            "error": None
        }
        
        provenance = None
        max_iterations = 10
        iteration = 0
        provenance_complete = False
        
        while iteration < max_iterations and not provenance_complete:
            iteration += 1
            
            iteration_trace = {
                "iteration": iteration,
                "response": None,
                "tool_calls": []
            }
            
            try:
                response = self.client.chat.completions.create(

                    model=self.model_name,
                    tools=[PROVENANCE_TOOL_CALL],
                    messages=messages,
                    **get_chat_reasoning_kwargs(self.model_name, uses_tools=True),
                    max_completion_tokens=self.max_completion_tokens,
                    extra_body=self.extra_body if self.extra_body else None
                )
                
                iteration_trace["response"] = response.model_dump()
                assistant_msg = response.choices[0].message.model_dump(exclude_none=True)
                messages.append(assistant_msg)

                tool_calls = response.choices[0].message.tool_calls or []
                
                for tc in tool_calls:
                    if tc.type != "function":
                        continue
                    
                    call_id = tc.id
                    
                    if tc.function.name == "extract_outbreak_provenance":
                        try:
                            function_args = json.loads(tc.function.arguments)
                        except JSONDecodeError:
                            msg = "JSON parsing error"
                            messages.append({
                                "role": "tool",
                                "tool_call_id": call_id,
                                "content": msg
                            })
                            iteration_trace["tool_calls"].append({
                                "name": "extract_outbreak_provenance",
                                "call_id": call_id,
                                "arguments": None,
                                "result": msg
                            })
                            continue
                        
                        try:
                            result = self.extractor.validate_provenance(
                                extracted_values=extracted_values,
                                **function_args
                            )
                        except Exception as e:
                            result = OutbreakProvenanceResult(
                                success=False,
                                message=f"Provenance validation error: {e}",
                                errors=[str(e)],
                                content={}
                            )
                        
                        output_msg = json.dumps({
                            "success": result.success,
                            "message": result.message,
                            "errors": result.errors
                        })
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": output_msg
                        })
                        
                        iteration_trace["tool_calls"].append({
                            "name": "extract_outbreak_provenance",
                            "call_id": call_id,
                            "arguments": function_args,
                            "result": result.message
                        })
                        
                        if result.success:
                            provenance = result.content
                            provenance["article_id"] = article_id
                            provenance["outbreak_index"] = outbreak_index
                            provenance_complete = True
                            
                            self.logger.info(
                                f"Successfully extracted provenance for outbreak {outbreak_index} "
                                f"in article {article_id}"
                            )
            
            except Exception as e:
                trace["error"] = str(e)
                self.logger.error(
                    f"Error during provenance extraction for article {article_id}, "
                    f"outbreak {outbreak_index}: {e}"
                )
                raise RuntimeError(
                    f"Outbreak provenance extraction failed for article {article_id}, "
                    f"outbreak {outbreak_index}: {e}"
                ) from e
            
            trace["iterations"].append(iteration_trace)
        
        if not provenance_complete:
            self.logger.warning(
                f"Provenance extraction incomplete for article {article_id}, "
                f"outbreak {outbreak_index}"
            )
        
        trace["provenance"] = provenance
        return provenance, trace
    
    def _flatten_provenance(self, article_id: str, outbreak_index: int, provenance_data: dict, extracted_values: dict) -> list:
        rows = []
        
        field_mapping = {
            "outbreak_country_excerpt": "outbreak_country",
            "outbreak_location_excerpt": "outbreak_location",
            "outbreak_start_excerpt": "outbreak_start",
            "outbreak_end_excerpt": "outbreak_end",
            "outbreak_duration_excerpt": "outbreak_duration_months",
            "outbreak_source_excerpt": "outbreak_source",
            "mode_of_detection_excerpt": "mode_of_detection",
            "method_of_case_definition_excerpt": "method_of_case_definition",
            "pre_outbreak_excerpt": "pre_outbreak",
            "cases_confirmed_excerpt": "cases_confirmed",
            "cases_probable_excerpt": "cases_probable",
            "cases_suspected_excerpt": "cases_suspected",
            "cases_unspecified_excerpt": "cases_unspecified",
            "cases_asymptomatic_excerpt": "cases_asymptomatic",
            "cases_severe_excerpt": "cases_severe",
            "deaths_excerpt": "deaths",
            "asymptomatic_transmission_excerpt": "asymptomatic_transmission_described",
            "population_size_excerpt": "population_size_geographical_area",
            "sex_disaggregation_excerpt": "sex_disaggregation",
        }
        
        for excerpt_field, field_name in field_mapping.items():
            excerpt = provenance_data.get(excerpt_field)
            if excerpt:
                rows.append({
                    "article_id": article_id,
                    "outbreak_index": outbreak_index,
                    "field_name": field_name,
                    "value": extracted_values.get(field_name),
                    "excerpt": excerpt
                })
        
        return rows
    
    def _process_article(self, item: tuple[int, pd.Series]) -> tuple[list[dict], list[dict]]:
        idx, row = item
        article_id = row.get("article_id")
        if article_id is None or (isinstance(article_id, float) and pd.isna(article_id)):
            article_id = str(idx)
        else:
            article_id = str(article_id)

        article_text = row.get("fulltext", "")

        if not article_text or (isinstance(article_text, float) and pd.isna(article_text)):
            self.logger.warning(f"Empty text for article {article_id}, skipping")
            return [], []

        has_outbreaks, _ = self.screen_article(article_text, article_id)

        if has_outbreaks and self.extraction_enabled:
            outbreaks, prov_rows, _ = self.extract_outbreaks(article_text, article_id)
            return outbreaks, prov_rows if self.provenance_enabled else []

        return [], []

    def run(self) -> pd.DataFrame:
        self.logger.info(
            f"Starting outbreak extraction for {self.pathogen} with {len(self.fulltext)} articles"
        )
        
        all_outbreaks = []
        all_provenance = []
        rows = list(self.fulltext.iterrows())

        for outbreaks, prov_rows in run_with_optional_thread_pool(
            rows,
            self._process_article,
            self.article_concurrency,
            desc="Processing articles",
        ):
            all_outbreaks.extend(outbreaks)
            if self.provenance_enabled and prov_rows:
                all_provenance.extend(prov_rows)

        output_path = self.output_outbreaks_file
        if output_path is None:
            output_path = os.path.join(self.log_dir, "extracted_outbreaks.csv")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if all_outbreaks and self.extraction_enabled:
            outbreaks_df = pd.DataFrame(all_outbreaks)
        else:
            outbreaks_df = pd.DataFrame()

        outbreaks_df.to_csv(output_path, index=False)
        self.logger.info(f"Saved extracted outbreaks to {output_path}")

        if self.provenance_enabled and all_provenance:
            excerpt_path = str(output_path).replace(".csv", "_excerpt.csv")
            Path(excerpt_path).parent.mkdir(parents=True, exist_ok=True)
            provenance_df = pd.DataFrame(all_provenance)
            provenance_df.to_csv(excerpt_path, index=False)
            self.logger.info(f"Saved provenance excerpts to {excerpt_path}")
        
        return outbreaks_df


class Runner(OutbreakExtractionRunner):
    def __init__(self, config, logger: Optional[logging.Logger] = None):
        start_time = dt.datetime.now()
        run_id = start_time.strftime("%Y-%m-%d_%H-%M-%S")

        log_dir = Path(config.log_dir) / f"data_extraction_outbreaks_dumps_{run_id}"
        log_dir.mkdir(parents=True, exist_ok=True)

        client = OpenAI(base_url=config.base_url, api_key=config.api_key)

        df = prepare_article_fulltext_dataframe(config, logger=logger)

        if "to_data_extract" in df.columns:
            df = df[df["to_data_extract"] == True].copy()
            
        df = apply_extraction_sample(df, config, logger=logger)

        super().__init__(
            client=client,
            run_id=run_id,
            model_name=config.model_name,
            pathogen=config.pathogen,
            fulltext=df[["title", "fulltext", "article_id"]] if "title" in df.columns else df[["fulltext", "article_id"]],
            extraction_enabled_bool=bool(getattr(config, "data_value_extraction_enabled_bool", True)),
            provenance_enabled=bool(getattr(config, "data_extraction_provenance_enabled", True)),
            log_dir=str(log_dir),
            output_outbreaks_file=str(config.data_extraction_outbreaks_path),
            max_completion_tokens=getattr(config, "max_completion_tokens", None),
            article_concurrency=get_data_extraction_concurrency(config),
        )

        if logger is not None:
            for h in list(self.logger.handlers):
                try:
                    logger.addHandler(h)
                except Exception:
                    pass


def parse_args():
    parser = ArgumentParser(description="Run outbreak extraction.")
    parser.add_argument("--pathogen", type=str, required=True, help="Pathogen name")
    parser.add_argument("--model_name", type=str, required=True, help="Model name")
    parser.add_argument("--port", type=int, default=8000, help="vLLM server port")
    parser.add_argument("--api_key", type=str, default="6767", help="vLLM server API key")

    parser.add_argument("--fulltext_screening_path", type=str, required=True)
    parser.add_argument("--data_extraction_outbreaks_path", type=str, required=True)
    parser.add_argument("--log_dir", type=str, required=True)

    parser.add_argument("--data_value_extraction_enabled_bool", type=str2bool, default=True)
    parser.add_argument("--data_extraction_provenance_enabled", type=str2bool, default=True)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    config = _CLIConfig(args)
    runner = Runner(config)
    runner.run()
