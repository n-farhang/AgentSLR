# src/ocr/run.py
from __future__ import annotations

from typing import Any, Callable


def _load_runner(ocr_client: str) -> Callable[[Any, Any], int]:
    if ocr_client == "mistral":
        from src.ocr.clients.mistral import run_ocr as runner

        return runner

    if ocr_client == "glm":
        from src.ocr.clients.glm import run_ocr as runner

        return runner

    if ocr_client == "paddle":
        from src.ocr.clients.paddle import run_ocr as runner

        return runner

    raise ValueError(f"Unsupported OCR client: {ocr_client}")


def run_ocr_stage(config, logger=None) -> int:
    if logger is not None:
        logger.info(
            "Starting OCR stage with client=%s input_source=%s",
            config.ocr_client,
            config.ocr_input_source,
        )
    runner = _load_runner(config.ocr_client)
    return runner(config, logger)
