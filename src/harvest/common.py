# src/harvest/common.py

from __future__ import annotations

import hashlib
import math
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_COLUMNS = [
    "article_id",
    "source",
    "pmid",
    "pmcid",
    "doi",
    "title",
    "authors",
    "journal",
    "year",
    "abstract",
    "url",
    "openalex_id",
    "openalex_pdf_url",
    "pathogen",
    "query",
    "harvested_at",
    "downloaded",
    "downloaded_path",
    "download_attempted_at",
    "download_source",
    "download_error",
]

PDF_MAGIC_BYTES = b"%PDF"
MIN_PDF_SIZE = 1024
MAX_PDF_SIZE = 500 * 1024 * 1024
USER_AGENT = "AgentSLR/1.0 (scholarly research tool)"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def emit_log(logger: Any, level: str, message: str) -> None:
    if logger is not None and hasattr(logger, level):
        getattr(logger, level)(message)
        return
    print(message)


def is_nan(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        return math.isnan(value)
    return False


def norm_text(value: str | None) -> str:
    if not value or is_nan(value):
        return ""
    cleaned = str(value).lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_doi(doi: str | None) -> str | None:
    if not doi or is_nan(doi):
        return None
    cleaned = str(doi).strip()
    if cleaned.lower() == "nan":
        return None
    cleaned = cleaned.replace("doi:", "").strip()
    cleaned = re.sub(r"^https?://(dx\.)?doi\.org/", "", cleaned).strip()
    return cleaned.lower() if cleaned else None


def normalize_pmid(pmid: str | None) -> str | None:
    if not pmid or is_nan(pmid):
        return None
    # Convert float like 3940312.0 → "3940312" before regex
    if isinstance(pmid, float):
        pmid = str(int(pmid))
    else:
        pmid = str(pmid).strip()
    if pmid.lower() == "nan":
        return None
    match = re.search(r"(\d+)", pmid)
    return match.group(1) if match else None


def normalize_pmcid(pmcid: str | None) -> str | None:
    if not pmcid or is_nan(pmcid):
        return None
    cleaned = str(pmcid).strip().upper()
    if cleaned == "NAN":
        return None
    if not cleaned.startswith("PMC"):
        match = re.search(r"(\d+)", cleaned)
        if not match:
            return None
        cleaned = f"PMC{match.group(1)}"
    match = re.search(r"(PMC\d+)", cleaned)
    return match.group(1) if match else None


def generate_article_id(record: dict[str, Any]) -> str:
    pmid = normalize_pmid(record.get("pmid"))
    if pmid:
        return f"PMID_{pmid}"

    doi = normalize_doi(record.get("doi"))
    if doi:
        return f"DOI_{hashlib.md5(doi.encode()).hexdigest()[:12]}"

    pmcid = normalize_pmcid(record.get("pmcid"))
    if pmcid:
        return pmcid

    openalex_id = record.get("openalex_id")
    if openalex_id and not is_nan(openalex_id):
        return f"OA_{hashlib.md5(str(openalex_id).encode()).hexdigest()[:12]}"

    title = record.get("title")
    if title and not is_nan(title):
        return f"TITLE_{hashlib.md5(str(title).encode()).hexdigest()[:12]}"

    return f"UUID_{uuid.uuid4().hex[:12]}"


def build_dedupe_key(record: dict[str, Any]) -> tuple[Any, ...]:
    pmid = normalize_pmid(record.get("pmid"))
    if pmid:
        return ("pmid", pmid)

    doi = normalize_doi(record.get("doi"))
    if doi:
        return ("doi", doi)

    pmcid = normalize_pmcid(record.get("pmcid"))
    if pmcid:
        return ("pmcid", pmcid)

    openalex_id = record.get("openalex_id")
    if openalex_id and not is_nan(openalex_id):
        return ("openalex_id", str(openalex_id).strip())

    title = norm_text(record.get("title"))
    year = str(record.get("year") or "").strip()
    if title and year:
        return ("title_year", title, year)
    if title:
        return ("title", title)
    return ("uuid", uuid.uuid4().hex)


def can_merge(base: dict[str, Any], incoming: dict[str, Any]) -> bool:
    pairs = (
        (normalize_pmid(base.get("pmid")), normalize_pmid(incoming.get("pmid"))),
        (normalize_doi(base.get("doi")), normalize_doi(incoming.get("doi"))),
        (normalize_pmcid(base.get("pmcid")), normalize_pmcid(incoming.get("pmcid"))),
    )
    for left, right in pairs:
        if left and right and left != right:
            return False
    return True


def merge_records(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    if not can_merge(base, incoming):
        return dict(base)

    merged = dict(base)
    source_a = str(merged.get("source") or "").strip()
    source_b = str(incoming.get("source") or "").strip()
    if source_a and source_b and source_a != source_b:
        merged["source"] = "Both"
    elif source_b and not source_a:
        merged["source"] = source_b

    merged["pmid"] = normalize_pmid(merged.get("pmid")) or normalize_pmid(incoming.get("pmid"))
    merged["pmcid"] = normalize_pmcid(merged.get("pmcid")) or normalize_pmcid(incoming.get("pmcid"))
    merged["doi"] = normalize_doi(merged.get("doi")) or normalize_doi(incoming.get("doi"))
    merged["openalex_id"] = merged.get("openalex_id") or incoming.get("openalex_id")
    merged["openalex_pdf_url"] = merged.get("openalex_pdf_url") or incoming.get("openalex_pdf_url")
    merged["title"] = merged.get("title") or incoming.get("title")
    merged["authors"] = merged.get("authors") or incoming.get("authors")
    merged["journal"] = merged.get("journal") or incoming.get("journal")
    merged["year"] = merged.get("year") or incoming.get("year")
    merged["abstract"] = merged.get("abstract") or incoming.get("abstract")
    merged["url"] = merged.get("url") or incoming.get("url")
    merged["pathogen"] = merged.get("pathogen") or incoming.get("pathogen")
    merged["query"] = merged.get("query") or incoming.get("query")
    merged["harvested_at"] = merged.get("harvested_at") or incoming.get("harvested_at")
    return merged


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=200, pool_maxsize=200)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session


class RateLimiter:
    def __init__(self, requests_per_second: float):
        self.min_interval = 0.0 if requests_per_second <= 0 else 1.0 / requests_per_second
        self._last_call = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()


class ThreadSafeRateLimiter:
    def __init__(self, requests_per_second: float):
        self.min_interval = 0.0 if requests_per_second <= 0 else 1.0 / requests_per_second
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_call = time.monotonic()


def ensure_harvest_columns(
    dataframe: pd.DataFrame,
    preserve_extra: bool = True,
) -> pd.DataFrame:
    extras = [col for col in dataframe.columns if col not in DEFAULT_COLUMNS] if preserve_extra else []
    for column in DEFAULT_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = None
    return dataframe[DEFAULT_COLUMNS + extras]


def write_progress(dataframe: pd.DataFrame, output_path: str | Path) -> None:
    dataframe.to_csv(output_path, index=False)
