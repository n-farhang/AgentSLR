# src/screening/common.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from utils.openai_wrapper import OpenAIResponsesWrapper, OpenAIWrapper


ABSTRACT_SCREENING_COLUMNS = [
    "ai4epi_abstract_response",
    "ai4epi_abstract_decision",
    "to_ocr",
    "screening_timestamp",
]

FULLTEXT_SCREENING_COLUMNS = [
    "ai4epi_fulltext_response",
    "ai4epi_fulltext_decision",
    "to_data_extract",
    "fulltext_timestamp",
    "fulltext_trace_id",
]


def emit_log(logger: Any, level: str, message: str) -> None:
    if logger is not None and hasattr(logger, level):
        getattr(logger, level)(message)
        return
    print(message)


def save_csv(dataframe: pd.DataFrame, filepath: str | Path) -> None:
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(path, index=False)


def truthy_mask(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    normalized = series.fillna(False).astype(str).str.strip().str.lower()
    return normalized.isin(["true", "t", "1", "yes", "y"])


def apply_sample(
    dataframe: pd.DataFrame,
    sample_size: int | None,
    sample_seed: int,
    logger: Any = None,
    label: str = "records",
) -> pd.DataFrame:
    if sample_size is None or len(dataframe) <= sample_size:
        return dataframe

    sampled = dataframe.sample(n=sample_size, random_state=sample_seed).sort_index()
    emit_log(
        logger,
        "info",
        f"Sampling {sample_size} of {len(dataframe)} {label} with seed={sample_seed}",
    )
    return sampled


def get_max_tokens_kwargs(config) -> dict[str, int]:
    if not config.responses_api and "gpt-oss" not in config.model_name.lower():
        return {"max_completion_tokens": config.max_completion_tokens}
    return {"max_output_tokens": config.max_completion_tokens + 32768}


def build_model(config, trace_dir: str | None = None):
    if config.responses_api or "gpt-oss" in config.model_name.lower():
        return OpenAIResponsesWrapper(
            model_name=config.model_name,
            base_url=config.base_url,
            api_key=config.api_key,
            reasoning_effort=config.reasoning_effort,
            max_output_tokens=config.max_completion_tokens + 32768,
            save_traces=config.save_traces,
            trace_dir=trace_dir,
        )

    return OpenAIWrapper(
        model_name=config.model_name,
        base_url=config.base_url,
        api_key=config.api_key,
        reasoning_effort=config.reasoning_effort,
        max_completion_tokens=config.max_completion_tokens,
        save_traces=config.save_traces,
        trace_dir=trace_dir,
        async_flag=config.hit_async,
    )


def update_rows_by_index(
    base_dataframe: pd.DataFrame,
    updated_dataframe: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    output = base_dataframe.copy()
    for column in columns:
        if column not in output.columns:
            output[column] = None
        output.loc[updated_dataframe.index, column] = updated_dataframe[column]
    return output


def merge_columns_by_article_id(
    markdown_dataframe: pd.DataFrame,
    screening_dataframe: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    if "article_id" not in markdown_dataframe.columns or "article_id" not in screening_dataframe.columns:
        raise ValueError("Both dataframes must contain 'article_id' to merge screening columns.")

    source_columns = ["article_id", *columns]
    source_dataframe = screening_dataframe[source_columns].drop_duplicates(subset=["article_id"])
    merged = markdown_dataframe.merge(
        source_dataframe,
        on="article_id",
        how="left",
        suffixes=("", "__screening"),
    )

    for column in columns:
        screening_column = f"{column}__screening"
        if screening_column not in merged.columns:
            continue
        if column in markdown_dataframe.columns:
            merged[column] = merged[column].combine_first(merged[screening_column])
        else:
            merged[column] = merged[screening_column]
        merged = merged.drop(columns=[screening_column])

    return merged
