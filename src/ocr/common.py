# src/ocr/common.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.screening.common import apply_sample, emit_log, save_csv, truthy_mask


OCR_COLUMNS = [
    "markdown_content",
    "markdown_path",
    "ocr_client",
    "ocr_model_name",
    "ocr_status",
    "ocr_error",
    "ocr_num_pages",
    "ocr_elapsed_seconds",
    "ocr_processed_at",
]

DOWNLOADED_FLAG_CANDIDATES = ["downloaded", "is_downloaded", "pdf_downloaded"]
PDF_PATH_CANDIDATES = [
    "downloaded_path",
    "downloaded_pdf_path",
    "pdf_path",
    "local_pdf_path",
    "download_path",
    "file_path",
]
SUCCESS_STATUSES = {"success", "skipped"}


def first_existing_column(dataframe: pd.DataFrame, candidates: list[str]) -> str:
    for column in candidates:
        if column in dataframe.columns:
            return column
    raise KeyError(f"Missing required column. Tried: {candidates}")


def get_pdf_path_column(dataframe: pd.DataFrame) -> str:
    return first_existing_column(dataframe, PDF_PATH_CANDIDATES)


def ensure_ocr_columns(
    dataframe: pd.DataFrame,
    client_name: str,
    model_name: str,
) -> pd.DataFrame:
    output = dataframe.copy()
    for column in OCR_COLUMNS:
        if column not in output.columns:
            output[column] = None
    output["markdown_content"] = output["markdown_content"].fillna("")
    output["ocr_client"] = client_name
    output["ocr_model_name"] = model_name
    return output


def has_successful_ocr(row: pd.Series) -> bool:
    status = str(row.get("ocr_status", "") or "").strip().lower()
    markdown_path = str(row.get("markdown_path", "") or "").strip()
    return status in SUCCESS_STATUSES and bool(markdown_path) and Path(markdown_path).exists()


def read_markdown(markdown_path: str | Path) -> str:
    return Path(markdown_path).read_text(encoding="utf-8", errors="ignore")


def resolve_pdf_path(pdf_value: str, config, input_path: Path) -> Path:
    pdf_path = Path(str(pdf_value)).expanduser()
    if pdf_path.is_absolute():
        return pdf_path

    candidates = [
        config.harvest_root / pdf_path,
        input_path.parent / pdf_path,
        Path.cwd() / pdf_path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return (config.harvest_root / pdf_path).resolve()


def expand_ocr_devices(device_value: str | None, gpu_prefix: str = "cuda") -> list[str]:
    normalized = str(device_value or "").strip()
    if not normalized or normalized.lower() == "auto":
        try:
            import torch

            if torch.cuda.is_available():
                devices = []
                for index in range(torch.cuda.device_count()):
                    try:
                        free_bytes, total_bytes = torch.cuda.mem_get_info(index)
                        used_ratio = 1.0 - (free_bytes / total_bytes)
                        if used_ratio <= 0.25:
                            devices.append(f"{gpu_prefix}:{index}")
                    except Exception:
                        devices.append(f"{gpu_prefix}:{index}")
                if devices:
                    return devices
                return [f"{gpu_prefix}:{index}" for index in range(torch.cuda.device_count())]
        except Exception:
            pass
        return ["cpu"]

    devices = [item.strip() for item in normalized.split(",") if item.strip()]
    return devices or ["cpu"]


def load_ocr_input_dataframe(config, logger: Any = None) -> tuple[Path, pd.DataFrame, str]:
    input_path = config.resolve_ocr_input_path()
    if not input_path.exists():
        raise FileNotFoundError(f"OCR input not found: {input_path}")

    emit_log(logger, "info", f"Loading OCR input from: {input_path}")
    dataframe = pd.read_csv(input_path)
    pdf_path_column = get_pdf_path_column(dataframe)
    pdf_mask = dataframe[pdf_path_column].notna() & (
        dataframe[pdf_path_column].astype(str).str.strip() != ""
    )

    if config.ocr_input_source == "abstract_screening":
        if "to_ocr" not in dataframe.columns:
            raise ValueError(
                "OCR input from abstract screening requires a 'to_ocr' column."
            )
        source_mask = truthy_mask(dataframe["to_ocr"])
        emit_log(
            logger,
            "info",
            f"Filtered to {int((source_mask & pdf_mask).sum())} abstract-screening rows marked for OCR.",
        )
    else:
        downloaded_column = first_existing_column(
            dataframe,
            DOWNLOADED_FLAG_CANDIDATES,
        )
        source_mask = truthy_mask(dataframe[downloaded_column])
        emit_log(
            logger,
            "info",
            f"Filtered to {int((source_mask & pdf_mask).sum())} downloaded PDF rows for OCR.",
        )

    dataframe = dataframe.loc[source_mask & pdf_mask].copy()
    if len(dataframe) == 0:
        raise ValueError("No PDFs available for OCR after filtering the selected input source.")

    dataframe = apply_sample(
        dataframe,
        getattr(config, "sample_size", None),
        getattr(config, "sample_seed", 7),
        logger=logger,
        label="OCR rows",
    )
    return input_path, dataframe, pdf_path_column


def persist_ocr_output(dataframe: pd.DataFrame, config, logger: Any = None) -> None:
    save_csv(dataframe, config.articles_with_markdown_path)
    emit_log(
        logger,
        "info",
        f"OCR output saved to: {config.articles_with_markdown_path}",
    )
