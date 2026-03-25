# src/screening/fulltext.py
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
from tqdm import tqdm
import re

from src.screening.common import (
    ABSTRACT_SCREENING_COLUMNS,
    FULLTEXT_SCREENING_COLUMNS,
    apply_sample,
    build_model,
    emit_log,
    get_max_tokens_kwargs,
    merge_columns_by_article_id,
    save_csv,
    truthy_mask,
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


def _load_markdown_dataframe(config, logger=None) -> tuple[Path, pd.DataFrame]:
    input_path = config.resolve_markdown_input_path()
    if not input_path.exists():
        raise FileNotFoundError(f"Full-text screening input not found: {input_path}")

    emit_log(logger, "info", f"Loading full-text screening input from: {input_path}")
    dataframe = pd.read_csv(input_path)
    if "markdown_content" not in dataframe.columns:
        raise ValueError(
            "No markdown content found in the input file. Run OCR first to convert PDFs to markdown."
        )
    return input_path, dataframe


def _merge_abstract_screening_if_needed(
    markdown_dataframe: pd.DataFrame,
    config,
    logger=None,
) -> pd.DataFrame:
    if config.fulltext_screening_mode == "direct_fulltext":
        markdown_dataframe["relevant_for_fulltext_screening"] = True
        return markdown_dataframe

    if config.fulltext_screening_mode == "on_ai4epi_abstracts":
        if "ai4epi_abstract_decision" not in markdown_dataframe.columns:
            if not config.abstract_screening_path.exists():
                raise FileNotFoundError(
                    "Abstract screening results not found. Run abstract screening first or pass a markdown CSV with ai4epi_abstract_* columns."
                )

            abstract_dataframe = pd.read_csv(config.abstract_screening_path)
            merge_columns = [
                column
                for column in ABSTRACT_SCREENING_COLUMNS
                if column in abstract_dataframe.columns
            ]
            markdown_dataframe = merge_columns_by_article_id(
                markdown_dataframe,
                abstract_dataframe,
                merge_columns,
            )
            save_csv(markdown_dataframe, config.articles_with_markdown_path)
            emit_log(
                logger,
                "info",
                f"Merged abstract screening columns into: {config.articles_with_markdown_path}",
            )

        if "ai4epi_abstract_decision" not in markdown_dataframe.columns:
            raise ValueError(
                "Conditioned full-text screening requires 'ai4epi_abstract_decision' to be present."
            )

        markdown_dataframe["relevant_for_fulltext_screening"] = (
            markdown_dataframe["ai4epi_abstract_decision"].fillna("").astype(str).str.upper() == "INCLUDE"
        )
        return markdown_dataframe

    if config.fulltext_screening_mode == "on_perg_abstracts":
        required_columns = ["perg_fulltext_result", "perg_abstract_result", "Covidence #", "perg_subset"]
        merge_columns = [
            column
            for column in required_columns
            if column not in markdown_dataframe.columns
        ]
        if merge_columns:
            if not config.abstract_screening_path.exists():
                raise FileNotFoundError(
                    "Abstract screening results not found. Run abstract screening first or pass a markdown CSV with the required PERG columns."
                )

            abstract_dataframe = pd.read_csv(config.abstract_screening_path)
            if not all(column in abstract_dataframe.columns for column in required_columns):
                raise ValueError(
                    "Expected columns ['perg_fulltext_result', 'perg_abstract_result', 'Covidence #', 'perg_subset'] "
                    "not found in abstract screening results file. Please ensure you are using the correct file with PERG annotations for full-text screening."
                )

            markdown_dataframe = merge_columns_by_article_id(
                markdown_dataframe,
                abstract_dataframe,
                merge_columns,
            )
            save_csv(markdown_dataframe, config.articles_with_markdown_path)
            emit_log(
                logger,
                "info",
                f"Merged PERG screening columns into: {config.articles_with_markdown_path}",
            )

        missing_columns = [column for column in required_columns if column not in markdown_dataframe.columns]
        if missing_columns:
            raise ValueError(
                f"Expected PERG columns {missing_columns} in markdown input after merge for conditioned full-text screening."
            )

        markdown_dataframe["relevant_for_fulltext_screening"] = (
            markdown_dataframe["perg_abstract_result"].fillna("").astype(str).str.upper() == "INCLUDE"
        )
        return markdown_dataframe

    raise ValueError(f"Unsupported full-text screening mode: {config.fulltext_screening_mode}")


def run_fulltext_screening(config, logger=None) -> int:
    _, dataframe = _load_markdown_dataframe(config, logger)
    dataframe = _merge_abstract_screening_if_needed(dataframe, config, logger)

    df_with_markdown = dataframe[dataframe["markdown_content"].notna()].copy()
    if "downloaded" in df_with_markdown.columns:
        df_with_markdown = df_with_markdown[truthy_mask(df_with_markdown["downloaded"])].copy()

    if config.fulltext_screening_mode != "direct_fulltext":
        df_with_markdown = df_with_markdown[df_with_markdown["relevant_for_fulltext_screening"] == True].copy()

    if len(df_with_markdown) == 0:
        raise ValueError("No markdown files available for full-text screening after filtering.")

    df_with_markdown = apply_sample(
        df_with_markdown,
        config.sample_size,
        config.sample_seed,
        logger=logger,
        label="full-text-screening rows",
    )

    emit_log(logger, "info", f"Conducting full-text review on {len(df_with_markdown)} papers")

    user_prompt_template = get_prompt(
        stage="fulltext_review",
        pathogen=config.pathogen,
    )

    titles = df_with_markdown["title"].fillna("").tolist()
    fulltexts = df_with_markdown["markdown_content"].fillna("").tolist()
    user_prompts = [
        user_prompt_template.format(title=title, fulltext=fulltext)
        for title, fulltext in zip(titles, fulltexts)
    ]

    start_time = dt.datetime.now()
    run_id = start_time.strftime("%Y-%m-%d_%H-%M-%S")

    trace_dir = None
    if config.save_traces:
        trace_dir = Path(config.log_dir) / f"fulltext_screening_dumps_{run_id}"
        emit_log(logger, "info", f"Reasoning traces will be saved to: {trace_dir}")

    model = build_model(
        config,
        trace_dir=str(trace_dir) if trace_dir else None,
    )

    for column in FULLTEXT_SCREENING_COLUMNS:
        if column not in df_with_markdown.columns:
            df_with_markdown[column] = None
    df_with_markdown["to_data_extract"] = False

    emit_log(logger, "info", f"Results will be saved to: {config.fulltext_screening_path}")
    emit_log(logger, "info", f"Run ID: {run_id}")
    emit_log(
        logger,
        "info",
        f"Reasoning effort: {config.reasoning_effort}, max_completion_tokens: {config.max_completion_tokens}",
    )

    batch_size = getattr(config, "fulltext_screening_batch_size", 64)
    concurrency = getattr(config, "fulltext_screening_concurrency", 8)

    for start in tqdm(range(0, len(user_prompts), batch_size), desc="Screening full texts"):
        batch_prompts = user_prompts[start : start + batch_size]
        batch_indices = df_with_markdown.index[start : start + batch_size]

        trace_ids = None
        if config.save_traces:
            trace_ids = [f"fulltext_{run_id}_{idx}" for idx in batch_indices]

        batch_responses = model.generate_many(
            batch_prompts,
            concurrency=concurrency,
            reasoning_effort=config.reasoning_effort,
            trace_ids=trace_ids,
            **get_max_tokens_kwargs(config),
        )

        for i, response in enumerate(batch_responses):
            idx = df_with_markdown.index[start + i]
            current_timestamp = dt.datetime.now().isoformat()
            df_with_markdown.at[idx, "ai4epi_fulltext_response"] = response
            df_with_markdown.at[idx, "ai4epi_fulltext_decision"] = parse_decision(response)
            df_with_markdown.at[idx, "to_data_extract"] = (
                df_with_markdown.at[idx, "ai4epi_fulltext_decision"] == "INCLUDE"
            )
            df_with_markdown.at[idx, "fulltext_timestamp"] = current_timestamp

            if config.save_traces and trace_ids:
                df_with_markdown.at[idx, "fulltext_trace_id"] = trace_ids[i]

        save_csv(df_with_markdown, config.fulltext_screening_path)
        emit_log(
            logger,
            "info",
            (
                f"Processed {min(start + batch_size, len(user_prompts))}/{len(user_prompts)} papers "
                f"- saved to {config.fulltext_screening_path}"
            ),
        )

    emit_log(
        logger,
        "info",
        f"Full-text screening decisions distribution: {df_with_markdown['ai4epi_fulltext_decision'].value_counts().to_dict()}",
    )
    emit_log(
        logger,
        "info",
        (
            f"Full-text screening summary: total={len(df_with_markdown)} "
            f"included={int(df_with_markdown['to_data_extract'].sum())}"
        ),
    )
    save_csv(df_with_markdown, config.fulltext_screening_path)
    return 0
