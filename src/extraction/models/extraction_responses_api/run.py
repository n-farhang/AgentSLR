# src/extraction/models/extraction_responses_api/run.py
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
    prepare_article_fulltext_dataframe,
    run_with_optional_thread_pool,
)
from .extractor import ModelExtractor, ModelExtractionResult, ModelProvenanceResult
from .tools import MODEL_TOOL_CALL, PROVENANCE_TOOL_CALL


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
        self.data_extraction_models_path = Path(args.data_extraction_models_path)

        self.data_value_extraction_enabled_bool = bool(args.data_value_extraction_enabled_bool)
        self.data_extraction_provenance_enabled = bool(args.data_extraction_provenance_enabled)


class ModelExtractionRunner:
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
        output_models_file: Optional[str] = None,
        article_concurrency: int = 1,
    ):
        self.client = client
        self.run_id = run_id
        self.model_name = model_name
        self.pathogen = pathogen
        self.fulltext = fulltext
        self.extraction_enabled = extraction_enabled_bool
        self.provenance_enabled = provenance_enabled
        self.output_models_file = output_models_file
        self.article_concurrency = max(1, int(article_concurrency))
        self._append_lock = Lock()

        self.extractor = ModelExtractor()

        self.start_time = dt.datetime.now()

        if log_dir is None:
            self.log_dir = (
                f"model_extraction/logs/"
                f"{self.start_time.strftime('%Y-%m-%d_%H-%M-%S')}_{run_id}/{self.pathogen}"
            )
        else:
            self.log_dir = str(log_dir)

        self.traces_dir = os.path.join(self.log_dir, "traces")

        self.logger = self._init_logger()

        self.system_prompt = f"""You are an epidemiologist specializing in infectious disease modeling. Extract information about transmission models from scientific articles.

# Study Objectives
This systematic review collates transmission models, outbreaks and parameters for {self.pathogen}."""

        self.screening_prompt = self._load_prompt("screening")
        self.extraction_prompt = self._load_prompt("extraction")

    def _init_logger(self) -> logging.Logger:
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.traces_dir, exist_ok=True)

        logger = logging.getLogger(f"model_extraction_{self.run_id}")
        logger.setLevel(logging.INFO)

        if logger.handlers:
            logger.handlers.clear()

        fh = logging.FileHandler(f"{self.log_dir}/extraction.log")
        fh.setLevel(logging.INFO)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

        return logger

    def _load_prompt(self, prompt_type: str) -> str:
        prompt_path = f"model_extraction/prompts/{prompt_type}.md"

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

        input_list = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": article_text},
        ]

        trace = {
            "stage": "screening",
            "article_id": article_id,
            "timestamp": dt.datetime.now().isoformat(),
            "input": input_list.copy(),
            "response": None,
            "decision": None,
            "error": None,
        }

        try:
            response = self.client.responses.create(
                model=self.model_name,
                input=input_list,
                reasoning={"effort": "high"},
            )

            trace["response"] = response.model_dump()

            answer = response.output[-1].content[0].text.strip()

            if answer.lower() == "true":
                answer = "True"
            else:
                answer = "False"

            result = answer == "True"
            trace["decision"] = result

            self.logger.info(f"Screening article {article_id}: {answer}")

            log_entry = {
                "article_id": article_id,
                "screening_decision": result,
                "model_response": answer,
                "timestamp": dt.datetime.now().isoformat(),
            }

            self._append_jsonl(os.path.join(self.log_dir, "screening.jsonl"), log_entry)

            self._save_trace(article_id, trace)

            return result, trace

        except Exception as e:
            self.logger.error(f"Error screening article {article_id}: {e}")
            trace["error"] = str(e)
            self._save_trace(article_id, trace)
            return False, trace

    def extract_models(self, article_text: str, article_id: str) -> tuple[list[dict], list[dict], dict]:
        prompt = self.system_prompt + "\n\n" + self.extraction_prompt

        input_list = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": article_text},
        ]

        trace = {
            "stage": "extraction",
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
                "tool_calls": [],
            }

            try:
                response = self.client.responses.create(
                    model=self.model_name,
                    tools=[MODEL_TOOL_CALL],
                    input=input_list,
                    reasoning={"effort": "high"},
                )

                iteration_trace["response"] = response.model_dump()
                input_list.extend(response.output)

                tool_called = False
                for item in response.output:
                    if item.type != "function_call":
                        continue

                    if item.name != "extract_model_data":
                        continue

                    tool_called = True
                    call_id = item.call_id

                    try:
                        function_args = json.loads(item.arguments)
                    except JSONDecodeError as e:
                        self.logger.error(
                            f"Failed to parse tool arguments for article {article_id}: {e}"
                        )
                        error_message = (
                            f"JSON parsing error: {e}. "
                            f"Could not parse arguments. Please check your JSON formatting."
                        )
                        input_list.append(
                            {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": error_message,
                            }
                        )
                        iteration_trace["tool_calls"].append(
                            {
                                "name": item.name,
                                "call_id": call_id,
                                "arguments": None,
                                "result": error_message,
                            }
                        )
                        continue

                    try:
                        result = self.extractor.validate_model(**function_args)
                    except Exception as e:
                        self.logger.error(
                            f"Validation error for article {article_id}: {e}"
                        )
                        result = ModelExtractionResult(
                            success=False,
                            message=f"Validation error: {e}",
                            errors=[str(e)],
                            content={},
                        )

                    input_list.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": result.message,
                        }
                    )

                    iteration_trace["tool_calls"].append(
                        {
                            "name": item.name,
                            "call_id": call_id,
                            "arguments": function_args,
                            "validation_result": {
                                "success": result.success,
                                "message": result.message,
                                "errors": result.errors,
                            },
                        }
                    )

                    if result.success:
                        result.content["article_id"] = article_id
                        result.content["model_index"] = len(extractions) + 1
                        result.content["extraction_timestamp"] = dt.datetime.now().isoformat()
                        extractions.append(result.content)
                        trace["extractions"].append(result.content)

                        self.logger.info(
                            f"Successfully extracted model {len(extractions)} "
                            f"from article {article_id}"
                        )
                    else:
                        self.logger.warning(
                            f"Validation failed for model in article {article_id}: "
                            f"{result.message}"
                        )

                trace["iterations"].append(iteration_trace)

                if not tool_called:
                    break

            except Exception as e:
                self.logger.error(f"Error during extraction for article {article_id}: {e}")
                trace["error"] = str(e)
                break

        self._save_trace(article_id, trace)

        for extraction in extractions:
            self._append_jsonl(os.path.join(self.log_dir, "extractions.jsonl"), extraction)

        provenance_rows = []
        if self.provenance_enabled and extractions:
            for idx, extraction in enumerate(extractions):
                provenance, prov_trace = self.extract_provenance(
                    article_text, article_id, extraction, model_index=idx + 1
                )
                self._append_jsonl(
                    os.path.join(self.log_dir, "provenance_traces.jsonl"),
                    {
                        "stage": "provenance",
                        "article_id": article_id,
                        "model_index": idx + 1,
                        "timestamp": dt.datetime.now().isoformat(),
                        "trace": prov_trace,
                    },
                )
                if provenance is not None:
                    matching_extraction = next(
                        (
                            m
                            for m in extractions
                            if m.get("article_id") == article_id and m.get("model_index") == (idx + 1)
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
        model_index: int = 1,
    ) -> tuple[Optional[dict], dict]:
        try:
            with open("model_extraction/prompts/provenance.md", "r") as f:
                provenance_prompt_text = f.read()
        except FileNotFoundError:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            provenance_prompt_path = os.path.join(script_dir, "prompts", "provenance.md")
            with open(provenance_prompt_path, "r") as f:
                provenance_prompt_text = f.read()

        prompt = self.system_prompt + "\n\n" + provenance_prompt_text

        extracted_summary = f"""# Extracted Model Data (Model {model_index})
Model Type: {extracted_values.get('model_type', 'N/A')}
Compartmental Type: {extracted_values.get('compartmental_type', 'N/A')}
Stochastic/Deterministic: {extracted_values.get('stoch_deter', 'N/A')}
Transmission Route: {extracted_values.get('transmission_route', 'N/A')}
Assumptions: {extracted_values.get('assumptions', 'N/A')}
Interventions: {extracted_values.get('interventions_type', 'N/A')}
Coding Language: {extracted_values.get('coding_language', 'N/A')}
Data Available: {extracted_values.get('is_data_used_available', 'N/A')}
"""

        input_list = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"{extracted_summary}\n\n# Article Text\n{article_text}"},
        ]

        trace = {
            "article_id": article_id,
            "model_index": model_index,
            "timestamp": dt.datetime.now().isoformat(),
            "input": input_list.copy(),
            "iterations": [],
            "provenance": None,
            "error": None,
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
                "tool_calls": [],
            }

            try:
                response = self.client.responses.create(
                    model=self.model_name,
                    tools=[PROVENANCE_TOOL_CALL],
                    input=input_list,
                    reasoning={"effort": "high"},
                )

                iteration_trace["response"] = response.model_dump()
                input_list.extend(response.output)

                for item in response.output:
                    if item.type != "function_call":
                        continue

                    call_id = item.call_id

                    if item.name == "extract_model_provenance":
                        try:
                            function_args = json.loads(item.arguments)
                        except JSONDecodeError:
                            msg = "JSON parsing error"
                            input_list.append(
                                {
                                    "type": "function_call_output",
                                    "call_id": call_id,
                                    "output": msg,
                                }
                            )
                            iteration_trace["tool_calls"].append(
                                {
                                    "name": item.name,
                                    "call_id": call_id,
                                    "arguments": None,
                                    "result": msg,
                                }
                            )
                            continue

                        try:
                            result = self.extractor.validate_provenance(
                                extracted_values=extracted_values,
                                **function_args,
                            )
                        except Exception as e:
                            result = ModelProvenanceResult(
                                success=False,
                                message=f"Provenance validation error: {e}",
                                errors=[str(e)],
                                content={},
                            )

                        output_msg = json.dumps(
                            {"success": result.success, "message": result.message, "errors": result.errors}
                        )

                        input_list.append(
                            {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": output_msg,
                            }
                        )

                        iteration_trace["tool_calls"].append(
                            {
                                "name": item.name,
                                "call_id": call_id,
                                "arguments": function_args,
                                "result": result.message,
                            }
                        )

                        if result.success:
                            provenance = result.content
                            provenance["article_id"] = article_id
                            provenance["model_index"] = model_index
                            provenance_complete = True

                            self.logger.info(
                                f"Successfully extracted provenance for model {model_index} "
                                f"in article {article_id}"
                            )

            except Exception as e:
                trace["error"] = str(e)
                self.logger.error(
                    f"Error during provenance extraction for article {article_id}, "
                    f"model {model_index}: {e}"
                )
                break

            trace["iterations"].append(iteration_trace)

        if not provenance_complete:
            self.logger.warning(
                f"Provenance extraction incomplete for article {article_id}, "
                f"model {model_index}"
            )

        trace["provenance"] = provenance
        return provenance, trace

    def _flatten_provenance(self, article_id: str, model_index: int, provenance_data: dict, extracted_values: dict) -> list:
        rows = []

        single_fields = {
            "model_type_excerpt": "model_type",
            "compartmental_type_excerpt": "compartmental_type",
            "stoch_deter_excerpt": "stoch_deter",
            "coding_language_excerpt": "coding_language",
            "data_availability_excerpt": "is_data_used_available",
        }

        for excerpt_field, field_name in single_fields.items():
            excerpt = provenance_data.get(excerpt_field)
            if excerpt:
                rows.append(
                    {
                        "article_id": article_id,
                        "model_index": model_index,
                        "field_name": field_name,
                        "value": extracted_values.get(field_name),
                        "excerpt": excerpt,
                    }
                )

        multi_fields = {
            "transmission_route_excerpts": "transmission_route",
            "assumptions_excerpts": "assumptions",
            "interventions_type_excerpts": "interventions_type",
        }

        for excerpt_field, field_name in multi_fields.items():
            excerpts_dict = provenance_data.get(excerpt_field, {})
            for value, excerpt in excerpts_dict.items():
                rows.append(
                    {
                        "article_id": article_id,
                        "model_index": model_index,
                        "field_name": field_name,
                        "value": value,
                        "excerpt": excerpt,
                    }
                )

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

        has_models, _ = self.screen_article(article_text, article_id)

        if has_models and self.extraction_enabled:
            models, prov_rows, _ = self.extract_models(article_text, article_id)
            return models, prov_rows if self.provenance_enabled else []

        return [], []

    def run(self) -> pd.DataFrame:
        self.logger.info(
            f"Starting model extraction for {self.pathogen} with {len(self.fulltext)} articles"
        )

        all_models = []
        all_provenance = []
        rows = list(self.fulltext.iterrows())

        for models, prov_rows in run_with_optional_thread_pool(
            rows,
            self._process_article,
            self.article_concurrency,
            desc="Processing articles",
        ):
            all_models.extend(models)
            if self.provenance_enabled and prov_rows:
                all_provenance.extend(prov_rows)

        output_path = self.output_models_file
        if output_path is None:
            output_path = os.path.join(self.log_dir, "extracted_models.csv")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if all_models and self.extraction_enabled:
            models_df = pd.DataFrame(all_models)
        else:
            models_df = pd.DataFrame()

        models_df.to_csv(output_path, index=False)
        self.logger.info(f"Saved extracted models to {output_path}")

        if self.provenance_enabled and all_provenance:
            excerpt_path = str(output_path).replace(".csv", "_excerpt.csv")
            Path(excerpt_path).parent.mkdir(parents=True, exist_ok=True)
            provenance_df = pd.DataFrame(all_provenance)
            provenance_df.to_csv(excerpt_path, index=False)
            self.logger.info(f"Saved provenance excerpts to {excerpt_path}")

        return models_df


class Runner(ModelExtractionRunner):
    def __init__(self, config, logger: Optional[logging.Logger] = None):
        start_time = dt.datetime.now()
        run_id = start_time.strftime("%Y-%m-%d_%H-%M-%S")

        log_dir = Path(config.log_dir) / f"data_extraction_models_dumps_{run_id}"
        log_dir.mkdir(parents=True, exist_ok=True)

        client = OpenAI(base_url=f"http://localhost:{config.port}/v1", api_key=config.api_key)

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
            output_models_file=str(config.data_extraction_models_path),
            article_concurrency=get_data_extraction_concurrency(config),
        )

        if logger is not None:
            for h in list(self.logger.handlers):
                try:
                    logger.addHandler(h)
                except Exception:
                    pass


def parse_args():
    parser = ArgumentParser(description="Run model extraction.")
    parser.add_argument("--pathogen", type=str, required=True, help="Pathogen name")
    parser.add_argument("--model_name", type=str, required=True, help="Model name")
    parser.add_argument("--port", type=int, default=8000, help="vLLM server port")
    parser.add_argument("--api_key", type=str, default="6767", help="vLLM server API key")

    parser.add_argument("--fulltext_screening_path", type=str, required=True)
    parser.add_argument("--data_extraction_models_path", type=str, required=True)
    parser.add_argument("--log_dir", type=str, required=True)

    parser.add_argument("--data_value_extraction_enabled_bool", type=str2bool, default=True)
    parser.add_argument("--data_extraction_provenance_enabled", type=str2bool, default=True)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    config = _CLIConfig(args)
    runner = Runner(config)
    runner.run()
