# src/harvest/pipeline.py

from __future__ import annotations

from typing import Any

import pandas as pd

from src.harvest.common import (
    RateLimiter,
    emit_log,
    ensure_harvest_columns,
    generate_article_id,
    make_session,
    normalize_doi,
    normalize_pmcid,
    normalize_pmid,
    utc_now_iso,
    write_progress,
)
from src.harvest.fetch_articles import download_articles
from src.harvest.fetch_metadata import harvest_metadata


def _ensure_identifiers(dataframe: pd.DataFrame, pathogen: str) -> pd.DataFrame:
    if "pathogen" not in dataframe.columns:
        dataframe["pathogen"] = pathogen
    else:
        dataframe["pathogen"] = dataframe["pathogen"].fillna(pathogen)

    if "article_id" not in dataframe.columns:
        dataframe["article_id"] = None

    for idx, row in dataframe.iterrows():
        pmid = normalize_pmid(row.get("pmid"))
        pmcid = normalize_pmcid(row.get("pmcid"))
        doi = normalize_doi(row.get("doi"))

        dataframe.at[idx, "pmid"] = pmid
        dataframe.at[idx, "pmcid"] = pmcid
        dataframe.at[idx, "doi"] = doi

        current_article_id = row.get("article_id")
        if not current_article_id or pd.isna(current_article_id):
            dataframe.at[idx, "article_id"] = generate_article_id(row.to_dict())

    return dataframe


def _load_metadata_input(config, logger: Any = None) -> pd.DataFrame:
    emit_log(logger, "info", f"Loading metadata from {config.metadata_input_path}")
    dataframe = pd.read_csv(
        config.metadata_input_path,
        dtype={"pmid": object, "pmcid": object, "doi": object},
    )
    dataframe = ensure_harvest_columns(dataframe, preserve_extra=True)
    dataframe = _ensure_identifiers(dataframe, config.pathogen)
    return dataframe


def final_dedup(dataframe: pd.DataFrame, logger: Any = None) -> pd.DataFrame:
    initial_count = len(dataframe)
    if "abstract" in dataframe.columns:
        dataframe = dataframe[
            dataframe["abstract"].notna() & (dataframe["abstract"].astype(str).str.strip() != "")
        ]

    dataframe = dataframe.drop_duplicates(subset=["article_id"])
    if "doi" in dataframe.columns:
        with_doi = dataframe[dataframe["doi"].notna()].drop_duplicates(subset=["doi"], keep="first")
        without_doi = dataframe[dataframe["doi"].isna()]
        dataframe = pd.concat([with_doi, without_doi], ignore_index=True)
        dataframe = dataframe.drop_duplicates(subset=["article_id"])

    emit_log(logger, "info", f"[{utc_now_iso()}] Final dedup: {initial_count} -> {len(dataframe)} records")
    return dataframe


def _build_metadata_frame(config, logger: Any = None) -> pd.DataFrame:
    if config.harvest_mode == "download_only":
        return _load_metadata_input(config, logger)

    session = make_session()
    records = harvest_metadata(
        pathogen=config.pathogen,
        session=session,
        oa_limiter=RateLimiter(config.openalex_rps),
        ncbi_limiter=RateLimiter(config.ncbi_rps),
        epmc_limiter=RateLimiter(config.europepmc_rps),
        config=config,
        logger=logger,
    )
    dataframe = pd.DataFrame(records)
    dataframe = ensure_harvest_columns(dataframe, preserve_extra=True)
    dataframe = _ensure_identifiers(dataframe, config.pathogen)
    return dataframe


def run_harvest_stage(config, logger: Any = None) -> int:
    emit_log(logger, "info", f"Running harvest stage for pathogen={config.pathogen} mode={config.harvest_mode}")
    emit_log(logger, "info", f"Harvest root: {config.harvest_root}")
    emit_log(logger, "info", f"PDF output dir: {config.pdf_dir}")
    emit_log(logger, "info", f"Harvest metadata path: {config.harvest_metadata_path}")
    emit_log(
        logger,
        "info",
        f"Harvest downloaded path: {config.harvest_downloaded_pdfs_path}",
    )

    dataframe = _build_metadata_frame(config, logger)

    if config.harvest_mode in {"full", "metadata_only"}:
        dataframe = final_dedup(dataframe, logger)

    dataframe.to_csv(config.harvest_metadata_path, index=False)
    write_progress(dataframe, config.progress_output_path)

    emit_log(logger, "info", f"[{utc_now_iso()}] Metadata rows ready for download: {len(dataframe)}")

    if config.harvest_mode == "metadata_only":
        emit_log(logger, "info", f"Metadata saved to: {config.harvest_metadata_path}")
        emit_log(logger, "info", f"Progress saved to: {config.progress_output_path}")
        return 0

    dataframe = download_articles(
        dataframe=dataframe,
        pdf_dir=str(config.pdf_dir),
        max_workers=config.article_downloading_workers,
        unpaywall_email=config.unpaywall_email or "xyz@gmail.com",
        ncbi_tool=config.ncbi_tool,
        ncbi_email=config.ncbi_email or "xyz@gmail.com",
        openalex_mailto=config.openalex_mailto,
        openalex_api_key=config.openalex_api_key,
        progress_path=str(config.progress_output_path),
        logger=logger,
        progress_every=config.progress_every,
    )
    dataframe.to_csv(config.harvest_downloaded_pdfs_path, index=False)

    downloaded_count = int((dataframe["downloaded"] == True).sum()) if "downloaded" in dataframe.columns else 0
    failed_count = len(dataframe) - downloaded_count

    emit_log(logger, "info", f"Complete: {config.pathogen}")
    emit_log(logger, "info", f"Total records: {len(dataframe)}")
    emit_log(logger, "info", f"Successfully downloaded: {downloaded_count}")
    emit_log(logger, "info", f"Failed: {failed_count}")
    emit_log(logger, "info", f"Metadata saved to: {config.harvest_metadata_path}")
    emit_log(logger, "info", f"Downloaded output saved to: {config.harvest_downloaded_pdfs_path}")
    emit_log(logger, "info", f"Progress saved to: {config.progress_output_path}")
    return 0
