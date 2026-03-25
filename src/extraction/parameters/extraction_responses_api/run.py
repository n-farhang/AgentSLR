# src/extraction/parameters/extraction_responses_api/run.py
import datetime as dt
import json
import logging
import os
import pandas as pd
import uuid

from json.decoder import JSONDecodeError
from threading import Lock
from tqdm import tqdm
from typing import Callable, Dict, Optional
from pathlib import Path

from openai import OpenAI

from src.extraction.common import (
    apply_extraction_sample,
    append_jsonl,
    get_data_extraction_concurrency,
    load_extraction_input_dataframe,
    run_with_optional_thread_pool,
)
from .tools import (
    AttackRateExtractor, GrowthRateExtractor, HumanDelayExtractor,
    MutationRateExtractor, RelativeContributionExtractor,
    ReproductionNumberExtractor, SeroprevalenceExtractor, SeverityExtractor
)
from .tools.extractor import ParameterExtractionResult, ParameterExtractor
from utils.screening_prompts import get_study_objectives
from utils.schemas import PARAMETER_CLASSES_MAPPING, VALID_PATHOGENS

MODULE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = MODULE_DIR / "prompts"
TOOLS_DIR = MODULE_DIR / "tools"


class ExtractionRunner:

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
        article_concurrency: int = 1,
    ):
        self.client = client
        self.run_id = run_id
        self.model_name = model_name
        self.pathogen = pathogen
        self.parameter_classes = parameter_classes
        self.fulltext = fulltext
        self.output_parameters_file = output_parameters_file
        self.article_concurrency = max(1, int(article_concurrency))
        self._append_lock = Lock()

        self.system_prompt = self._read_text(PROMPTS_DIR / "basic_instruction.md")
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
        os.makedirs(self.results_dir, exist_ok=True)

        self.logger = self._init_logger()

    def _init_logger(self) -> logging.Logger:
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.traces_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        
        logger = logging.getLogger(f"parameter_extraction_{self.run_id}")
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

    def screen_parameters(
        self, user_prompt: str, row: pd.Series,
    ) -> dict[str, bool]:
        screening_results = {}
        extractor = ParameterExtractor()
        screening_prompt = self.system_prompt + "\n" + self._read_text(
            PROMPTS_DIR / "screening.md"
        )

        article_id = str(row["article_id"])

        for parameter_class in self.parameter_classes:
            parameter_screening_prompt = screening_prompt + "\n" + self._read_text(
                TOOLS_DIR / parameter_class / "screening.md"
            )

            input_list = [
                {"role": "system", "content": parameter_screening_prompt},
                {"role": "user", "content": user_prompt},
            ]

            tool = extractor.SCREENING_TOOL_CALL

            trace = {
                "stage": "screening",
                "article_id": article_id,
                "parameter_class": parameter_class,
                "timestamp": dt.datetime.now().isoformat(),
                "input": input_list.copy(),
                "iterations": [],
                "decision": None,
                "annotations": None,
                "error": None
            }

            success = False
            contains_parameter = False
            annotations = None

            iteration = 0

            while not success:
                success = True
                iteration += 1

                iteration_trace = {
                    "iteration": iteration,
                    "response": None,
                    "tool_calls": []
                }

                try:
                    response = self.client.responses.create(
                        model=self.model_name,
                        tools=[tool],  
                        input=input_list,  
                        reasoning={"effort": "high"},
                    )
                except Exception as e:
                    self.logger.error(f"Encountered error during LLM call: {e}")
                    continue

                iteration_trace["response"] = response.model_dump()

                input_list += response.output

                for item in response.output:
                    if item.type == "function_call":
                        if item.name == tool["name"]:
                            function_args = {}
                            result = ParameterExtractionResult(
                                parameter=parameter_class,
                                success=False,
                                errors=[],
                                content={},
                                message=""
                            )
                            try:
                                function_args = json.loads(item.arguments)
                            except JSONDecodeError as e:
                                result = extractor.return_result(
                                    parameter=parameter_class,
                                    errors=[
                                        "The following arguments could not be parsed: "
                                        f"{item.arguments}"
                                    ],
                                )

                                iteration_trace["tool_calls"].append({
                                    "name": item.name,
                                    "call_id": item.call_id,
                                    "arguments": None,
                                    "result": result.message,
                                    "parse_error": str(e)
                                })

                            if function_args != {}:
                                try:
                                    result = extractor.extract_screening(
                                        parameter=parameter_class,
                                        **json.loads(item.arguments)
                                    )
                                except Exception as e:
                                    result = extractor.return_result(
                                        parameter=parameter_class,
                                        errors=[
                                            f"{tool['name']} failed with an error:\n{e}"],
                                    )

                                iteration_trace["tool_calls"].append({
                                    "name": item.name,
                                    "call_id": item.call_id,
                                    "arguments": function_args,
                                    "validation_result": {
                                        "success": result.success,
                                        "message": result.message,
                                        "errors": result.errors
                                    }
                                })

                            if not result.success:
                                success = False
                            else:
                                contains_parameter = result.content["contains_parameter"]
                                annotations = result.content["annotations"]

                            input_list.append({
                                "type": "function_call_output",
                                "call_id": item.call_id,
                                "output": json.dumps({
                                    "success": result.success,
                                    "message": result.message
                                })
                            })

                for item in response.output:
                    if item.type == "function_call":
                        success = False

                trace["iterations"].append(iteration_trace)

            screening_results[parameter_class] = contains_parameter

            trace["decision"] = contains_parameter
            trace["annotations"] = annotations

            os.makedirs(self.results_dir, exist_ok=True)

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

            total_positive = sum(screening_results.values())

            self.logger.info(
                f"Screening complete for article {article_id}: "
                f"{total_positive}/{len(self.parameter_classes)} parameter classes contain data"
            )


            self._save_trace(article_id, f"screening_{parameter_class}", trace)

        return screening_results

    def extract_structured_parameters_with_tool(
        self,
        parameter: str,
        system_prompt: str,
        user_prompt: str,
        tool: dict,
        function_call: Callable,
        extractor: ParameterExtractor,
        article_id: str,
        stage: str,
    ) -> tuple[list[dict], list[dict], dict]:
        
        input_list = [
            {"role": "system", "content": system_prompt},
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
            "error": None
        }

        success = False
        extraction: list[dict] = []
        iteration = 0

        while not success:
            success = True
            iteration += 1

            iteration_trace = {
                "iteration": iteration,
                "response": None,
                "tool_calls": []
            }

            try:
                response = self.client.responses.create(
                    model=self.model_name,
                    tools=[tool],  
                    input=input_list,
                    reasoning={"effort": "high"},
                )

            except Exception as e:
                self.logger.error(f"Encountered error during LLM call: {e}")
                trace["error"] = str(e)
                continue

            iteration_trace["response"] = response.model_dump()

            input_list += response.output

            for item in response.output:
                if item.type == "function_call":
                    if item.name == tool["name"]:
                        function_args = {}
                        try:
                            function_args = json.loads(item.arguments)
                        except JSONDecodeError as e:
                            result = extractor.return_result(
                                parameter=parameter,
                                errors=[
                                    "The following arguments could not be parsed: "
                                    f"{item.arguments}"
                                ],
                            )

                            iteration_trace["tool_calls"].append({
                                "name": item.name,
                                "call_id": item.call_id,
                                "arguments": None,
                                "result": result.message,
                                "parse_error": str(e)
                            })

                        if function_args != {}:
                            try:
                                result = function_call(
                                    parameter=parameter,
                                    **json.loads(item.arguments)
                                )
                            except Exception as e:
                                result = extractor.return_result(
                                    parameter=parameter,
                                    errors=[
                                        f"{tool['name']} failed with an error:\n{e}"],
                                )

                            iteration_trace["tool_calls"].append({
                                "name": item.name,
                                "call_id": item.call_id,
                                "arguments": function_args,
                                "validation_result": {
                                    "success": result.success,
                                    "message": result.message,
                                    "errors": result.errors
                                }
                            })

                        if not result.success:
                            success = False

                        else:
                            extraction.append({
                                "id": str(uuid.uuid4()),
                                **result.content
                            })

                        input_list.append({
                            "type": "function_call_output",
                            "call_id": item.call_id,
                            "output": json.dumps({
                                "success": result.success,
                                "message": result.message
                            })
                        })

            for item in response.output:
                if item.type == "function_call":
                    success = False
            
            trace["iterations"].append(iteration_trace)

        return extraction, input_list[2:], trace


    def extract_single_paper_parameters(self, row: pd.Series):
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
                    f"article_id {row['article_id']}. Skipping extraction."
                )
                continue

            if parameter not in self.EXTRACTORS:
                self.logger.info(
                    f"No extractor implemented for parameter type {parameter}. "
                    "Skipping extraction."
                )
                continue

            extractor = self.EXTRACTORS[parameter]()

            extraction_prompt = self.system_prompt + "\n" + self._read_text(
                PROMPTS_DIR / "value_extraction.md"
            )
            extraction_prompt += "\n" + self._read_text(
                TOOLS_DIR / parameter / "value_extraction.md"
            )

            extracted_parameters, reasoning_trace, extraction_trace = (
                self.extract_structured_parameters_with_tool(
                    parameter=parameter,
                    system_prompt=extraction_prompt,
                    user_prompt=user_prompt,
                    tool=extractor.TOOL_CALL,
                    function_call=extractor.extract_value,
                    extractor=extractor,
                    article_id=article_id,
                    stage=f"value_extraction_{parameter}",
                )
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
                self.logger.info(
                    f"No parameters extracted for {parameter} in "
                    f"article_id {row['article_id']}. Skipping."
                )
                continue

            uncertainty_prompt = self.system_prompt + "\n" + self._read_text(
                PROMPTS_DIR / "uncertainty.md"
            )

            extracted_parameters_with_uncertainty = []

            for idx, (extracted_parameter, value_reasoning_trace) in enumerate(zip(extracted_parameters, reasoning_trace)):
                self.logger.info(
                    f"Extracting uncertainty info for parameter: {extracted_parameter}"
                )

                extracted_uncertainty_context, uncertainty_reasoning_trace, uncertainty_trace = (
                    self.extract_structured_parameters_with_tool(
                        parameter=parameter + " uncertainty",
                        system_prompt=uncertainty_prompt,
                        user_prompt=user_prompt,
                        tool=extractor.UNCERTAINTY_TOOL_CALL,
                        function_call=extractor.extract_uncertainty_info,
                        extractor=extractor,
                        article_id=article_id,
                        stage=f"uncertainty_{parameter}_{idx}",
                    )
                )

                if len(extracted_uncertainty_context) > 0:
                    result = extracted_uncertainty_context[0]
                    extracted_parameters_with_uncertainty.append(
                        {
                            **extracted_parameter,
                            **result,
                            "value_reasoning_trace": value_reasoning_trace,
                        }
                    )

                    self._append_jsonl(
                        os.path.join(self.results_dir, "uncertainties.jsonl"),
                        {
                            "article_id": article_id,
                            "our_screening_decision": row.get("our_screening_decision", None),
                            "parameter_class": parameter,
                            "extraction": {**extracted_parameter, **result},
                            "timestamp": dt.datetime.now().isoformat()
                        }
                    )

                    self.logger.info(
                        f"Successfully extracted uncertainty info for {parameter} "
                        f"parameter {idx+1}/{len(extracted_parameters)} in article {article_id}"
                    )

                    self._save_trace(article_id, f"uncertainty_{parameter}_{idx}", uncertainty_trace)

            population_prompt = self.system_prompt + "\n" + self._read_text(
                PROMPTS_DIR / "population.md"
            )

            extracted_parameters_with_population = []

            for idx, extracted_parameter_with_uncertainty in enumerate(extracted_parameters_with_uncertainty):
                extracted_parameter = {
                    k: v for k, v in extracted_parameter_with_uncertainty.items()
                    if k != "value_reasoning_trace"
                }
                value_reasoning_trace = extracted_parameter_with_uncertainty["value_reasoning_trace"]
                self.logger.info(
                    f"Extracting population info for parameter: {extracted_parameter}"
                )

                extracted_population_context, population_reasoning_trace, population_trace = (
                    self.extract_structured_parameters_with_tool(
                        parameter=parameter + " population",
                        system_prompt=population_prompt,
                        user_prompt=user_prompt,
                        tool=extractor.POPULATION_TOOL_CALL,
                        function_call=extractor.extract_population_info,
                        extractor=extractor,
                        article_id=article_id,
                        stage=f"population_{parameter}_{idx}",
                    )
                )

                if len(extracted_population_context) > 0:
                    result = extracted_population_context[0]
                    extracted_parameters_with_population.append(
                        {
                            **extracted_parameter,
                            **result,
                        }
                    )

                    self._append_jsonl(
                        os.path.join(self.results_dir, "populations.jsonl"),
                        {
                            "article_id": article_id,
                            "our_screening_decision": row.get("our_screening_decision", None),
                            "parameter_class": parameter,
                            "extraction": {**extracted_parameter, **result},
                            "timestamp": dt.datetime.now().isoformat()
                        }
                    )

                    self.logger.info(
                            f"Successfully extracted population info for {parameter} "
                            f"parameter {idx+1}/{len(extracted_parameters_with_uncertainty)} in article {article_id}"
                        )

                    self._save_trace(article_id, f"population_{parameter}_{idx}", population_trace)

                    self._append_jsonl(
                        os.path.join(self.results_dir, "raw_parameters.jsonl"),
                        {
                            "article_id": article_id,
                            "our_screening_decision": row.get("our_screening_decision", None),
                            "parameter_class": parameter,
                            "extraction": {**extracted_parameter, **result},
                            "aggregated": False,
                            "timestamp": dt.datetime.now().isoformat()
                        }
                    )

            aggregated_parameters = []
            if len(extracted_parameters_with_population) > 1:
                self.logger.info(
                    "There are multiple extracted parameters. Attempting aggregation..."
                )

                aggregation_user_prompt = user_prompt + "\n"
                aggregation_user_prompt += (
                    f"# Extracted parameters:\n"
                    f"{extracted_parameters_with_population}"
                )

                aggregation_prompt = self.system_prompt + "\n" + self._read_text(
                    PROMPTS_DIR / "aggregation.md"
                )

                aggregated_parameters, aggregation_reasoning_trace, aggregation_trace = (
                    self.extract_structured_parameters_with_tool(
                        parameter=parameter + " aggregation",
                        system_prompt=aggregation_prompt,
                        user_prompt=aggregation_user_prompt,
                        tool=extractor.AGGREGATION_TOOL_CALL,
                        function_call=extractor.extract_aggregated_parameters,
                        extractor=extractor,
                        article_id=article_id,
                        stage=f"aggregation_{parameter}",
                    )
                )

                for result in aggregated_parameters:
            
                    self._append_jsonl(
                        os.path.join(self.results_dir, "aggregations.jsonl"),
                        {
                            "article_id": article_id,
                            "our_screening_decision": row.get("our_screening_decision", None),
                            "parameter_class": parameter,
                            "extraction": result,
                            "timestamp": dt.datetime.now().isoformat()
                        }
                    )

                    self.logger.info(
                        f"Successfully aggregated parameter for {parameter} in article {article_id}"
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
        with open(os.path.join(self.log_dir, "results", "raw_parameters.jsonl"), "r") as f:
            raw_parameters = [json.loads(line) for line in f]

        uuids_in_aggregations = set()
        for entry in raw_parameters:
            if entry.get("aggregated", False):
                uuids_in_aggregations.update(
                    entry["extraction"].get("aggregated_ids", [])
                )
        final_parameters = [
            entry for entry in raw_parameters
            if entry["extraction"]["id"] not in uuids_in_aggregations
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

            raise(e)

        self.write_final_parameters()
        metadata["duration_seconds"] = (
            (dt.datetime.now() - self.start_time).total_seconds()
        )
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=4)


class Runner(ExtractionRunner):
    def __init__(self, config, logger: Optional[logging.Logger] = None):
        start_time = dt.datetime.now()

        if config.pathogen not in VALID_PATHOGENS:
            raise ValueError(
                f"Invalid pathogen: {config.pathogen}. Must be one of {VALID_PATHOGENS}"
            )

        if len(config.parameter_classes) == 1 and config.parameter_classes[0] == "all":
            config.parameter_classes = list(PARAMETER_CLASSES_MAPPING.values()).copy()
        else:
            if any(
                param not in PARAMETER_CLASSES_MAPPING.values()
                for param in config.parameter_classes
            ):
                raise ValueError(
                    f"Invalid parameter classes: {config.parameter_classes}. "
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
            parameter_classes=config.parameter_classes,
            fulltext=fulltext,
            log_dir=str(log_dir),
            output_parameters_file=str(config.data_extraction_parameters_path),
            article_concurrency=get_data_extraction_concurrency(config),
        )

        if logger is not None:
            for h in list(self.logger.handlers):
                try:
                    logger.addHandler(h)
                except Exception:
                    pass
