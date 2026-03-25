# src/analysis/run.py
from __future__ import annotations

from src.analysis.models.writeup import run_models_writeup
from src.analysis.outbreaks.writeup import run_outbreaks_writeup
from src.analysis.parameters.writeup import run_parameters_writeup
from src.analysis.models.writeup_llm import run_models_writeup_llm
from src.analysis.outbreaks.writeup_llm import run_outbreaks_writeup_llm
from src.analysis.parameters.writeup_llm import run_parameters_writeup_llm


def _run_one(config, logger, report_type: str):
    if report_type == "parameters":
        raw_runner = run_parameters_writeup
        llm_runner = run_parameters_writeup_llm
        md_path = config.report_parameters_md
        manifest_path = config.report_parameters_manifest
    elif report_type == "models":
        raw_runner = run_models_writeup
        llm_runner = run_models_writeup_llm
        md_path = config.report_models_md
        manifest_path = config.report_models_manifest
    elif report_type == "outbreaks":
        raw_runner = run_outbreaks_writeup
        llm_runner = run_outbreaks_writeup_llm
        md_path = config.report_outbreaks_md
        manifest_path = config.report_outbreaks_manifest
    else:
        raise ValueError(f"Unsupported report type: {report_type}")

    result = {}
    if config.writeup_mode in {"raw", "both"}:
        logger.info("Generating raw %s report", report_type)
        raw_runner(config)

    if config.writeup_mode in {"llm", "both"}:
        if not md_path.exists() or not manifest_path.exists():
            logger.info(
                "Raw %s report missing; generating raw report before refinement",
                report_type,
            )
            raw_runner(config)
        logger.info("Running LLM refinement for %s report", report_type)
        result = llm_runner(config)

    return result


def run_writeup_stage(config, logger):
    stage_to_types = {
        "write_up": ["parameters", "models", "outbreaks"],
        "write_up_parameters": ["parameters"],
        "write_up_models": ["models"],
        "write_up_outbreaks": ["outbreaks"],
    }
    report_types = stage_to_types.get(config.stage)
    if report_types is None:
        raise ValueError(f"Unsupported write-up stage: {config.stage}")

    failed = []

    for report_type in report_types:
        try:
            _run_one(...)
        except Exception:
            logger.exception(...)
            failed.append(report_type)

    if failed:
        logger.error("Write-up failed for: %s", ", ".join(failed))
        return 1

    return 0
