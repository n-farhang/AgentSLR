# src/extraction/vllm_guided/runners.py
"""
vLLM Guided Runner classes.

These classes wrap the standard extraction runners and use guided JSON decoding
for the extraction step when running on vLLM backends.
"""

import datetime as dt
import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from openai import OpenAI

from src.extraction.common import (
    apply_extraction_sample,
    get_data_extraction_concurrency,
    prepare_article_fulltext_dataframe,
)
from ..models.extraction.run import ModelExtractionRunner
from ..outbreaks.extraction.run import OutbreakExtractionRunner

from .model_extraction import GuidedModelExtractor
from .outbreak_extraction import GuidedOutbreakExtractor
from .parameter_extraction import ParameterRunner


class VLLMGuidedModelRunner(ModelExtractionRunner):
    """
    Model extraction runner that uses guided JSON decoding for vLLM backends.
    
    This class overrides the extract_models method to use grammar-constrained
    decoding instead of tool calls.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guided_extractor = GuidedModelExtractor(
            client=self.client,
            model_name=self.model_name,
            logger=self.logger,
        )
    
    def extract_models(self, article_text: str, article_id: str) -> tuple[list[dict], list[dict], dict]:
        """
        Extract models using guided JSON decoding.
        
        Returns:
            Tuple of (list of model dicts, list of provenance rows, trace dict)
        """
        extractions, trace = self.guided_extractor.extract_models(
            article_text=article_text,
            article_id=article_id,
            system_prompt=self.system_prompt,
            extraction_prompt=self.extraction_prompt,
            max_completion_tokens=self.max_completion_tokens,
            extra_body=self.extra_body,
        )
        
        prov_rows = []
        
        if self.provenance_enabled and extractions:
            for model_index, model_data in enumerate(extractions):
                provenance, prov_trace = self.guided_extractor.extract_provenance(
                    article_text=article_text,
                    article_id=article_id,
                    model_data=model_data,
                    system_prompt=self.system_prompt,
                    max_completion_tokens=self.max_completion_tokens,
                    extra_body=self.extra_body,
                )
                
                if provenance:
                    rows = self._flatten_provenance(article_id, model_index, provenance, model_data)
                    prov_rows.extend(rows)
        
        self._save_trace(article_id, trace)
        
        return extractions, prov_rows, trace


class VLLMGuidedOutbreakRunner(OutbreakExtractionRunner):
    """
    Outbreak extraction runner that uses guided JSON decoding for vLLM backends.
    
    This class overrides the extract_outbreaks method to use grammar-constrained
    decoding instead of tool calls.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guided_extractor = GuidedOutbreakExtractor(
            client=self.client,
            model_name=self.model_name,
            logger=self.logger,
        )
    
    def extract_outbreaks(self, article_text: str, article_id: str) -> tuple[list[dict], list[dict], dict]:
        """
        Extract outbreaks using guided JSON decoding.
        
        Returns:
            Tuple of (list of outbreak dicts, list of provenance rows, trace dict)
        """
        extractions, trace = self.guided_extractor.extract_outbreaks(
            article_text=article_text,
            article_id=article_id,
            system_prompt=self.system_prompt,
            extraction_prompt=self.extraction_prompt,
            max_completion_tokens=self.max_completion_tokens,
            extra_body=self.extra_body,
        )
        
        prov_rows = []
        
        if self.provenance_enabled and extractions:
            for outbreak_index, outbreak_data in enumerate(extractions):
                provenance, prov_trace = self.guided_extractor.extract_provenance(
                    article_text=article_text,
                    article_id=article_id,
                    outbreak_data=outbreak_data,
                    system_prompt=self.system_prompt,
                    max_completion_tokens=self.max_completion_tokens,
                    extra_body=self.extra_body,
                )
                
                if provenance:
                    rows = self._flatten_provenance(article_id, outbreak_index, provenance, outbreak_data)
                    prov_rows.extend(rows)
        
        self._save_trace(article_id, trace)
        
        return extractions, prov_rows, trace


class ModelRunner(VLLMGuidedModelRunner):
    """
    Standard Runner interface for model extraction with vLLM guided decoding.
    
    This class provides the same interface as the standard Runner class
    but uses guided JSON decoding for extraction.
    """
    
    def __init__(self, config, logger: Optional[logging.Logger] = None):
        start_time = dt.datetime.now()
        run_id = start_time.strftime("%Y-%m-%d_%H-%M-%S")
        
        log_dir = Path(config.log_dir) / f"data_extraction_models_dumps_{run_id}"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        client = OpenAI(base_url=config.base_url, api_key=config.api_key)
        
        df = prepare_article_fulltext_dataframe(config, logger=logger)
        df = apply_extraction_sample(df, config, logger=logger)
        
        super().__init__(
            client=client,
            run_id=run_id,
            model_name=config.model_name,
            pathogen=config.pathogen,
            fulltext=df,
            extraction_enabled_bool=config.data_value_extraction_enabled_bool,
            provenance_enabled=config.data_extraction_provenance_enabled,
            log_dir=str(log_dir),
            output_models_file=str(config.data_extraction_models_path),
            max_completion_tokens=getattr(config, "max_completion_tokens", 98304),
            article_concurrency=get_data_extraction_concurrency(config),
        )
        
        if logger:
            self.logger = logger


class OutbreakRunner(VLLMGuidedOutbreakRunner):
    """
    Standard Runner interface for outbreak extraction with vLLM guided decoding.
    
    This class provides the same interface as the standard Runner class
    but uses guided JSON decoding for extraction.
    """
    
    def __init__(self, config, logger: Optional[logging.Logger] = None):
        start_time = dt.datetime.now()
        run_id = start_time.strftime("%Y-%m-%d_%H-%M-%S")
        
        log_dir = Path(config.log_dir) / f"data_extraction_outbreaks_dumps_{run_id}"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        client = OpenAI(base_url=config.base_url, api_key=config.api_key)
        
        df = prepare_article_fulltext_dataframe(config, logger=logger)
        df = apply_extraction_sample(df, config, logger=logger)
        
        super().__init__(
            client=client,
            run_id=run_id,
            model_name=config.model_name,
            pathogen=config.pathogen,
            fulltext=df,
            extraction_enabled_bool=config.data_value_extraction_enabled_bool,
            provenance_enabled=config.data_extraction_provenance_enabled,
            log_dir=str(log_dir),
            output_outbreaks_file=str(config.data_extraction_outbreaks_path),
            max_completion_tokens=getattr(config, "max_completion_tokens", None),
            article_concurrency=get_data_extraction_concurrency(config),
        )
        
        if logger:
            self.logger = logger
