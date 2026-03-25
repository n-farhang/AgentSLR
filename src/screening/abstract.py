# src/screening/abstract.py
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
from tqdm import tqdm
import re

from src.screening.common import (
    ABSTRACT_SCREENING_COLUMNS,
    apply_sample,
    build_model,
    emit_log,
    get_max_tokens_kwargs,
    save_csv,
    truthy_mask,
    update_rows_by_index,
)
from src.screening.prompts import get_prompt


def parse_decision(response: str) -> str:
    matches = re.findall(
        r"<decision>\s*(include|exclude|unclear)\s*</decision>",
        str(response),
        re.IGNORECASE,
    )
    if len(matches) == 1:
        return matches[0].upper()
    return "UNCLEAR"


def _load_input_dataframe(config, logger=None) -> tuple[Path, pd.DataFrame]:
    input_path = config.resolve_abstract_screening_input_path()
    if not input_path.exists():
        raise FileNotFoundError(f"Abstract screening input not found: {input_path}")

    emit_log(logger, "info", f"Loading abstract screening input from: {input_path}")
    return input_path, pd.read_csv(input_path)


def _filter_candidate_rows(
    dataframe: pd.DataFrame,
    config,
    input_path: Path,
    logger=None,
) -> pd.DataFrame:
    if "downloaded" not in dataframe.columns:
        return dataframe.copy()

    downloaded_mask = truthy_mask(dataframe["downloaded"])
    if input_path == config.harvest_metadata_path or config.article_doc_status == "metadata":
        emit_log(logger, "info", f"Screening {len(dataframe)} metadata rows without download filtering")
        return dataframe.copy()

    if downloaded_mask.any():
        filtered = dataframe.loc[downloaded_mask].copy()
        emit_log(logger, "info", f"Filtered to {len(filtered)} downloaded rows for abstract screening")
        return filtered

    emit_log(logger, "info", "No downloaded rows found; screening all available rows")
    return dataframe.copy()


def run_abstract_screening(config, logger=None) -> int:
    input_path, input_dataframe = _load_input_dataframe(config, logger)
    screening_dataframe = _filter_candidate_rows(input_dataframe, config, input_path, logger)
    screening_dataframe = apply_sample(
        screening_dataframe,
        config.sample_size,
        config.sample_seed,
        logger=logger,
        label="abstract-screening rows",
    )

    emit_log(logger, "info", f"Screening {len(screening_dataframe)} papers")

    user_prompt_template = get_prompt(
        stage="abstract_screening",
        pathogen=config.pathogen,
    )

    titles = screening_dataframe["title"].fillna("").tolist()
    abstracts = screening_dataframe["abstract"].fillna("").tolist()
    user_prompts = [
        user_prompt_template.format(title=title, abstract=abstract)
        for title, abstract in zip(titles, abstracts)
    ]

    start_time = dt.datetime.now()
    run_id = start_time.strftime("%Y-%m-%d_%H-%M-%S")

    trace_dir = None
    if config.save_traces:
        trace_dir = Path(config.log_dir) / f"abstract_screening_dumps_{run_id}"
        emit_log(logger, "info", f"Reasoning traces will be saved to: {trace_dir}")

    model = build_model(
        config,
        trace_dir=str(trace_dir) if trace_dir else None,
    )

    for column in ABSTRACT_SCREENING_COLUMNS:
        if column not in screening_dataframe.columns:
            screening_dataframe[column] = None
    screening_dataframe["to_ocr"] = False

    emit_log(logger, "info", f"Results will be saved to: {config.abstract_screening_path}")
    emit_log(logger, "info", f"Run ID: {run_id}")

    batch_size = getattr(config, "abstract_screening_batch_size", 64)
    concurrency = getattr(config, "abstract_screening_concurrency", 8)

    def persist_outputs() -> None:
        if "markdown_content" in input_dataframe.columns:
            reduced_dataframe = screening_dataframe.drop(columns=["markdown_content"], errors="ignore")
            save_csv(reduced_dataframe, config.abstract_screening_path)

            updated_markdown_dataframe = update_rows_by_index(
                input_dataframe,
                screening_dataframe,
                ["markdown_content", *ABSTRACT_SCREENING_COLUMNS],
            )
            save_csv(updated_markdown_dataframe, config.articles_with_markdown_path)
        else:
            save_csv(screening_dataframe, config.abstract_screening_path)

    for start in tqdm(range(0, len(user_prompts), batch_size), desc="Screening papers"):
        batch_prompts = user_prompts[start : start + batch_size]
        batch_indices = screening_dataframe.index[start : start + batch_size]

        trace_ids = None
        if config.save_traces:
            trace_ids = [f"abstract_{run_id}_{idx}" for idx in batch_indices]

        batch_responses = model.generate_many(
            batch_prompts,
            concurrency=concurrency,
            reasoning_effort=config.reasoning_effort,
            trace_ids=trace_ids,
            **get_max_tokens_kwargs(config),
        )

        for i, response in enumerate(batch_responses):
            idx = batch_indices[i]
            current_timestamp = dt.datetime.now().isoformat()
            screening_dataframe.at[idx, "ai4epi_abstract_response"] = response
            screening_dataframe.at[idx, "ai4epi_abstract_decision"] = parse_decision(response)
            screening_dataframe.at[idx, "to_ocr"] = (
                screening_dataframe.at[idx, "ai4epi_abstract_decision"] == "INCLUDE"
            )
            screening_dataframe.at[idx, "screening_timestamp"] = current_timestamp

        persist_outputs()

    included_dataframe = screening_dataframe[screening_dataframe["to_ocr"] == True]

    if "markdown_content" in input_dataframe.columns:
        emit_log(
            logger,
            "info",
            f"Updated markdown CSV with abstract decisions: {config.articles_with_markdown_path}",
        )

    emit_log(logger, "info", f"Included {len(included_dataframe)} papers for full-text review")
    emit_log(
        logger,
        "info",
        (
            f"Abstract screening summary: total={len(screening_dataframe)} "
            f"included={len(included_dataframe)} excluded={len(screening_dataframe) - len(included_dataframe)}"
        ),
    )
    return 0
