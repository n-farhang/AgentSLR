# src/extraction/vllm_guided/__init__.py
"""
vLLM Guided JSON Extraction Module

This module provides guided JSON decoding for vLLM-served models,
ensuring strict schema enforcement for extraction tasks.

Usage in s5_data_extract.py:
    from src.extraction.vllm_guided.runners import ModelRunner, OutbreakRunner
    
Or directly:
    from src.extraction.vllm_guided import GuidedModelExtractor, GuidedOutbreakExtractor
    from src.extraction.vllm_guided import is_vllm_backend
    
    if is_vllm_backend(client):
        guided = GuidedModelExtractor(client, model_name, logger)
        extractions, trace = guided.extract_models(...)
"""

from .model_extraction import GuidedModelExtractor
from .outbreak_extraction import GuidedOutbreakExtractor
from .parameter_extraction import GuidedParameterExtractionRunner
from .runners import ModelRunner, OutbreakRunner, ParameterRunner


def is_vllm_backend(client) -> bool:
    """Check if the OpenAI client is pointing to a vLLM server (localhost/0.0.0.0)."""
    try:
        base_url = str(client.base_url) if client.base_url else ""
        return any(host in base_url for host in ["0.0.0.0", "127.0.0.1", "localhost"])
    except Exception:
        return False


def is_vllm_backend_from_url(base_url: str) -> bool:
    """Check if a base URL points to a vLLM server (localhost/0.0.0.0)."""
    return any(host in base_url for host in ["0.0.0.0", "127.0.0.1", "localhost"])


__all__ = [
    'GuidedModelExtractor', 
    'GuidedOutbreakExtractor',
    'GuidedParameterExtractionRunner',
    'ModelRunner',
    'OutbreakRunner',
    'ParameterRunner',
    'is_vllm_backend',
    'is_vllm_backend_from_url',
]
