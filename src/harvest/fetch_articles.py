# src/harvest/fetch_articles.py

from __future__ import annotations

import errno
import os
import re
import shutil
import tempfile
import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import requests

from src.harvest.common import (
    MAX_PDF_SIZE,
    MIN_PDF_SIZE,
    PDF_MAGIC_BYTES,
    ThreadSafeRateLimiter,
    emit_log,
    ensure_dir,
    make_session,
    normalize_doi,
    normalize_pmcid,
    normalize_pmid,
    utc_now_iso,
    write_progress,
)


def validate_pdf_content(content: bytes) -> tuple[bool, str]:
    if not content:
        return False, "Empty content"
    if len(content) < MIN_PDF_SIZE:
        return False, f"File too small ({len(content)} bytes)"
    if len(content) > MAX_PDF_SIZE:
        return False, f"File too large ({len(content)} bytes)"
    if not content[:4].startswith(PDF_MAGIC_BYTES):
        header = content[:100].lower()
        if b"<!doctype" in header or b"<html" in header:
            return False, "Received HTML instead of PDF"
        return False, "Invalid PDF header"

    content_lower = content[:5000].lower()
    error_indicators = [
        b"access denied",
        b"unauthorized",
        b"403 forbidden",
        b"404 not found",
        b"subscription required",
        b"please login",
        b"sign in to access",
    ]
    for indicator in error_indicators:
        if indicator in content_lower:
            return False, f"PDF contains access error: {indicator.decode(errors='ignore')}"

    return True, ""


def validate_pdf_file(filepath: str | Path) -> tuple[bool, str]:
    try:
        with open(filepath, "rb") as handle:
            return validate_pdf_content(handle.read())
    except Exception as exc:
        return False, f"Error reading file: {exc}"


def sanitize_filename(title: str, max_length: int = 80) -> str:
    if not title:
        return "untitled"
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title)
    safe = re.sub(r"\s+", "_", safe).strip("._")
    if len(safe) > max_length:
        safe = safe[:max_length].rsplit("_", 1)[0]
    return safe or "untitled"


def generate_pdf_filename(record: dict[str, Any]) -> str:
    article_id = record.get("article_id")
    if article_id:
        return f"{article_id}.pdf"

    pmid = normalize_pmid(record.get("pmid"))
    if pmid:
        return f"PMID_{pmid}.pdf"

    pmcid = normalize_pmcid(record.get("pmcid"))
    if pmcid:
        return f"{pmcid}.pdf"

    doi = normalize_doi(record.get("doi"))
    if doi:
        from hashlib import md5

        return f"DOI_{md5(doi.encode()).hexdigest()[:12]}.pdf"

    title = record.get("title") or ""
    from hashlib import md5

    return f"{sanitize_filename(str(title), 40)}_{md5(str(title).encode()).hexdigest()[:8]}.pdf"


@dataclass
class DownloadResult:
    success: bool
    filepath: str | None = None
    source: str | None = None
    error: str | None = None
    attempted_sources: list[str] = field(default_factory=list)


class PDFDownloader:
    def __init__(
        self,
        unpaywall_email: str,
        ncbi_tool: str,
        ncbi_email: str,
        openalex_mailto: str | None = None,
        openalex_api_key: str | None = None,
        temp_dir: str | None = None,
    ):
        self.unpaywall_email = unpaywall_email
        self.ncbi_tool = ncbi_tool
        self.ncbi_email = ncbi_email
        self.openalex_mailto = openalex_mailto
        self.openalex_api_key = openalex_api_key
        self.temp_dir = temp_dir
        self._thread_local = threading.local()
        self._cache_lock = threading.Lock()
        self._idconv_cache: dict[str, dict[str, str | None]] = {}
        self._unpaywall_cache: dict[str, str | None] = {}
        self._openalex_cache: dict[str, str | None] = {}
        self._europepmc_cache: dict[str, str | None] = {}
        self.limiters = {
            "pmc_oa": ThreadSafeRateLimiter(10.0),
            "unpaywall": ThreadSafeRateLimiter(50.0),
            "europe_pmc": ThreadSafeRateLimiter(20.0),
            "openalex": ThreadSafeRateLimiter(30.0),
            "direct": ThreadSafeRateLimiter(20.0),
            "idconv": ThreadSafeRateLimiter(10.0),
        }

    def _session(self) -> requests.Session:
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = make_session()
            self._thread_local.session = session
        return session

    def _is_server_responsive(self, url: str) -> bool:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            host = parsed.netloc or parsed.path.split("/")[0]
            test_url = f"{parsed.scheme}://{host}/"
            self._session().head(test_url, timeout=(2, 5), allow_redirects=False)
            return True
        except Exception:
            return False

    def _download_to_temp(self, url: str, limiter_key: str) -> tuple[str | None, str]:
        if limiter_key == "direct" and not self._is_server_responsive(url):
            return None, "Server unreachable (quick check)"

        session = self._session()
        self.limiters[limiter_key].wait()
        headers = {"Accept": "application/pdf,*/*;q=0.9"}

        try:
            with session.get(
                url,
                timeout=(10, 30),
                allow_redirects=True,
                stream=True,
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    if response.status_code == 403:
                        return None, "Access forbidden (403)"
                    if response.status_code == 404:
                        return None, "Not found (404)"
                    if response.status_code == 429:
                        return None, "Rate limited (429)"
                    return None, f"HTTP {response.status_code}"

                temp_file = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".pdf",
                    dir=self.temp_dir,
                )
                temp_path = temp_file.name
                size = 0

                try:
                    for chunk in response.iter_content(chunk_size=1024 * 64):
                        if not chunk:
                            continue
                        size += len(chunk)
                        if size > MAX_PDF_SIZE:
                            temp_file.close()
                            os.remove(temp_path)
                            return None, f"File too large (> {MAX_PDF_SIZE} bytes)"
                        temp_file.write(chunk)

                    temp_file.close()
                    with open(temp_path, "rb") as handle:
                        header = handle.read(4)
                    if header != PDF_MAGIC_BYTES:
                        os.remove(temp_path)
                        return None, "Invalid PDF header"
                    return temp_path, ""
                except Exception as exc:
                    try:
                        temp_file.close()
                    except Exception:
                        pass
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                    return None, f"Stream error: {exc}"
        except requests.exceptions.Timeout:
            return None, "Request timeout"
        except requests.exceptions.ConnectionError:
            return None, "Connection error"
        except Exception as exc:
            return None, f"Download error: {exc}"

    def _pmc_idconv(self, identifier: str, idtype: str | None = None) -> dict[str, str | None]:
        key = f"{idtype or 'auto'}:{identifier}"
        with self._cache_lock:
            if key in self._idconv_cache:
                return self._idconv_cache[key]

        params: dict[str, Any] = {
            "ids": identifier,
            "format": "json",
            "tool": self.ncbi_tool,
            "email": self.ncbi_email,
        }
        if idtype:
            params["idtype"] = idtype

        self.limiters["idconv"].wait()
        response = self._session().get(
            "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/",
            params=params,
            timeout=(5, 15),
        )
        if response.status_code != 200:
            result = {"pmid": None, "pmcid": None, "doi": None}
            with self._cache_lock:
                self._idconv_cache[key] = result
            return result

        data = response.json()
        records = data.get("records") or []
        if records:
            first = records[0] or {}
            result = {
                "pmid": str(first.get("pmid")) if first.get("pmid") is not None else None,
                "pmcid": str(first.get("pmcid")) if first.get("pmcid") is not None else None,
                "doi": str(first.get("doi")) if first.get("doi") is not None else None,
            }
        else:
            result = {"pmid": None, "pmcid": None, "doi": None}

        with self._cache_lock:
            self._idconv_cache[key] = result
        return result

    def try_openalex_pdf(self, record: dict[str, Any]) -> tuple[str | None, str]:
        pdf_url = record.get("openalex_pdf_url")
        if not pdf_url:
            return None, "No PDF URL available"

        temp_path, error = self._download_to_temp(str(pdf_url), "openalex")
        if not temp_path:
            return None, error

        valid, validation_error = validate_pdf_file(temp_path)
        if valid:
            return temp_path, ""

        os.remove(temp_path)
        return None, f"Invalid PDF: {validation_error}"

    def try_openalex_lookup(self, doi: str) -> tuple[str | None, str]:
        from urllib.parse import quote

        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            return None, "Invalid DOI"

        with self._cache_lock:
            if normalized_doi in self._openalex_cache:
                cached = self._openalex_cache[normalized_doi]
                return (cached, "") if cached else (None, "No OA PDF in OpenAlex")

        params: dict[str, Any] = {}
        if self.openalex_mailto:
            params["mailto"] = self.openalex_mailto
        if self.openalex_api_key:
            params["api_key"] = self.openalex_api_key

        self.limiters["openalex"].wait()
        response = self._session().get(
            f"https://api.openalex.org/works/https://doi.org/{quote(normalized_doi, safe='')}",
            params=params,
            timeout=(5, 15),
        )
        if response.status_code != 200:
            with self._cache_lock:
                self._openalex_cache[normalized_doi] = None
            return None, f"OpenAlex lookup HTTP {response.status_code}"

        data = response.json() or {}
        pdf_url = (data.get("best_oa_location") or {}).get("url_for_pdf")
        with self._cache_lock:
            self._openalex_cache[normalized_doi] = pdf_url
        if not pdf_url:
            return None, "No OA PDF in OpenAlex"

        temp_path, error = self._download_to_temp(str(pdf_url), "openalex")
        if not temp_path:
            return None, error

        valid, validation_error = validate_pdf_file(temp_path)
        if valid:
            return temp_path, ""

        os.remove(temp_path)
        return None, f"Invalid PDF: {validation_error}"

    def try_europe_pmc_fulltext(self, record: dict[str, Any]) -> tuple[str | None, str]:
        pmid = normalize_pmid(record.get("pmid"))
        pmcid = normalize_pmcid(record.get("pmcid"))
        doi = normalize_doi(record.get("doi"))
        cache_key = pmcid or pmid or doi
        if not cache_key:
            return None, "No identifiers"

        with self._cache_lock:
            if cache_key in self._europepmc_cache:
                cached = self._europepmc_cache[cache_key]
                if not cached:
                    return None, "No PDF in Europe PMC"
                temp_path, error = self._download_to_temp(cached, "europe_pmc")
                if not temp_path:
                    return None, error
                valid, validation_error = validate_pdf_file(temp_path)
                if valid:
                    return temp_path, ""
                os.remove(temp_path)
                return None, f"Invalid PDF: {validation_error}"

        query_parts = []
        if pmcid:
            query_parts.append(f"PMCID:{pmcid}")
        if pmid:
            query_parts.append(f"EXT_ID:{pmid} SRC:MED")
        if doi:
            query_parts.append(f'DOI:"{doi}"')
        query = " OR ".join(f"({part})" for part in query_parts) if len(query_parts) > 1 else (query_parts[0] if query_parts else "")
        if not query:
            return None, "No query"

        self.limiters["europe_pmc"].wait()
        response = self._session().get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={
                "query": query,
                "format": "json",
                "resultType": "core",
                "pageSize": 1,
                "cursorMark": "*",
                "synonym": "FALSE",
            },
            timeout=(5, 15),
        )
        if response.status_code != 200:
            with self._cache_lock:
                self._europepmc_cache[cache_key] = None
            return None, f"Europe PMC HTTP {response.status_code}"

        data = response.json() or {}
        results = ((data.get("resultList") or {}).get("result")) or []
        if isinstance(results, dict):
            results = [results]

        pdf_url = None
        for result in results:
            full_text_urls = (result.get("fullTextUrlList") or {}).get("fullTextUrl")
            if not full_text_urls:
                continue
            if isinstance(full_text_urls, dict):
                full_text_urls = [full_text_urls]
            for item in full_text_urls:
                if not isinstance(item, dict):
                    continue
                candidate_url = item.get("url")
                document_format = str(item.get("documentFormat") or "").lower()
                document_style = str(item.get("documentStyle") or "").lower()
                if candidate_url and (
                    "pdf" in document_format
                    or "pdf" in document_style
                    or str(candidate_url).lower().endswith(".pdf")
                ):
                    pdf_url = candidate_url
                    break
            if pdf_url:
                break

        with self._cache_lock:
            self._europepmc_cache[cache_key] = pdf_url
        if not pdf_url:
            return None, "No PDF in Europe PMC"

        temp_path, error = self._download_to_temp(str(pdf_url), "europe_pmc")
        if not temp_path:
            return None, error

        valid, validation_error = validate_pdf_file(temp_path)
        if valid:
            return temp_path, ""

        os.remove(temp_path)
        return None, f"Invalid PDF: {validation_error}"

    def try_unpaywall(self, doi: str) -> tuple[str | None, str]:
        from urllib.parse import quote

        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            return None, "Invalid DOI"

        with self._cache_lock:
            if normalized_doi in self._unpaywall_cache:
                cached = self._unpaywall_cache[normalized_doi]
                if not cached:
                    return None, "No OA PDF in Unpaywall"
                temp_path, error = self._download_to_temp(cached, "direct")
                if not temp_path:
                    return None, error
                valid, validation_error = validate_pdf_file(temp_path)
                if valid:
                    return temp_path, ""
                os.remove(temp_path)
                return None, f"Invalid PDF: {validation_error}"

        self.limiters["unpaywall"].wait()
        response = self._session().get(
            f"https://api.unpaywall.org/v2/{quote(normalized_doi, safe='')}",
            params={"email": self.unpaywall_email},
            timeout=(5, 15),
        )
        if response.status_code == 404:
            with self._cache_lock:
                self._unpaywall_cache[normalized_doi] = None
            return None, "Not found in Unpaywall"
        if response.status_code != 200:
            with self._cache_lock:
                self._unpaywall_cache[normalized_doi] = None
            return None, f"Unpaywall HTTP {response.status_code}"

        data = response.json() or {}
        if not data.get("is_oa"):
            with self._cache_lock:
                self._unpaywall_cache[normalized_doi] = None
            return None, "Not OA"

        best_location = data.get("best_oa_location") or {}
        pdf_url = best_location.get("url_for_pdf") or best_location.get("url")
        if not pdf_url:
            for location in data.get("oa_locations", []) or []:
                pdf_url = location.get("url_for_pdf") or location.get("url")
                if pdf_url:
                    break

        with self._cache_lock:
            self._unpaywall_cache[normalized_doi] = pdf_url
        if not pdf_url:
            return None, "No OA URL"

        temp_path, error = self._download_to_temp(str(pdf_url), "direct")
        if not temp_path:
            return None, error

        valid, validation_error = validate_pdf_file(temp_path)
        if valid:
            return temp_path, ""

        os.remove(temp_path)
        return None, f"Invalid PDF: {validation_error}"

    def download_pdf(self, record: dict[str, Any]) -> DownloadResult:
        result = DownloadResult(success=False)
        doi = normalize_doi(record.get("doi"))

        sources: list[tuple[str, Any, dict[str, Any]]] = []
        if record.get("openalex_pdf_url"):
            sources.append(("OpenAlex_PDF_URL", self.try_openalex_pdf, {"record": record}))
        sources.append(("Europe_PMC_Fulltext", self.try_europe_pmc_fulltext, {"record": record}))
        if doi:
            sources.append(("Unpaywall", self.try_unpaywall, {"doi": doi}))
            sources.append(("OpenAlex_Lookup", self.try_openalex_lookup, {"doi": doi}))

        errors = []
        for source_name, fn, kwargs in sources:
            result.attempted_sources.append(source_name)
            temp_path = None
            try:
                temp_path, error = fn(**kwargs)
                if temp_path:
                    result.success = True
                    result.source = source_name
                    result.filepath = temp_path
                    return result
                errors.append(f"{source_name}: {error}")
            except Exception as exc:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                errors.append(f"{source_name}: Exception - {exc}")

        result.error = " | ".join(errors) if errors else "No sources attempted"
        return result


def process_record(
    idx: int,
    record: dict[str, Any],
    downloader: PDFDownloader,
    pdf_dir: str,
    total: int,
    current_success: int = 0,
) -> dict[str, Any]:
    output = dict(record)
    output["download_attempted_at"] = utc_now_iso()

    if output.get("downloaded") is True and output.get("downloaded_path"):
        path = str(output.get("downloaded_path"))
        if os.path.exists(path):
            valid, _ = validate_pdf_file(path)
            if valid:
                return output

    filename = generate_pdf_filename(output)
    filepath = os.path.join(pdf_dir, filename)
    if os.path.exists(filepath):
        valid, _ = validate_pdf_file(filepath)
        if valid:
            output["downloaded"] = True
            output["downloaded_path"] = filepath
            output["download_source"] = output.get("download_source") or "existing_file"
            output["download_error"] = None
            return output

    download_result = downloader.download_pdf(output)
    if download_result.success and download_result.filepath and os.path.exists(download_result.filepath):
        try:
            try:
                os.replace(download_result.filepath, filepath)
            except OSError as exc:
                if exc.errno == errno.EXDEV:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    shutil.move(download_result.filepath, filepath)
                else:
                    raise

            valid, validation_error = validate_pdf_file(filepath)
            if valid:
                output["downloaded"] = True
                output["downloaded_path"] = filepath
                output["download_source"] = download_result.source
                output["download_error"] = None
            else:
                try:
                    os.remove(filepath)
                except Exception:
                    pass
                output["downloaded"] = False
                output["downloaded_path"] = None
                output["download_source"] = None
                output["download_error"] = f"Validation failed: {validation_error}"
        except Exception as exc:
            output["downloaded"] = False
            output["downloaded_path"] = None
            output["download_source"] = None
            output["download_error"] = f"Save error: {exc}"
    else:
        output["downloaded"] = False
        output["downloaded_path"] = None
        output["download_source"] = None
        output["download_error"] = download_result.error

    return output


def _iter_todo_indices(dataframe: pd.DataFrame):
    for idx, row in dataframe.iterrows():
        downloaded = row.get("downloaded")
        downloaded_path = row.get("downloaded_path")
        if downloaded is True and isinstance(downloaded_path, str) and downloaded_path and os.path.exists(downloaded_path):
            valid, _ = validate_pdf_file(downloaded_path)
            if valid:
                continue
        yield idx


def download_articles(
    dataframe: pd.DataFrame,
    pdf_dir: str,
    max_workers: int,
    unpaywall_email: str,
    ncbi_tool: str,
    ncbi_email: str,
    openalex_mailto: str | None,
    openalex_api_key: str | None,
    progress_path: str,
    logger: Any = None,
    progress_every: int = 50,
) -> pd.DataFrame:
    temp_dir = os.path.join(pdf_dir, "_tmp")
    ensure_dir(temp_dir)

    for column in [
        "downloaded",
        "downloaded_path",
        "download_attempted_at",
        "download_source",
        "download_error",
    ]:
        if column not in dataframe.columns:
            dataframe[column] = None

    dataframe["downloaded"] = dataframe["downloaded"].apply(
        lambda value: True
        if str(value).lower() == "true"
        else (False if str(value).lower() == "false" else None)
    )

    total = len(dataframe)
    already_downloaded = int((dataframe["downloaded"] == True).sum())
    todo = list(_iter_todo_indices(dataframe))

    emit_log(logger, "info", f"[{utc_now_iso()}] Total records: {total}")
    emit_log(logger, "info", f"[{utc_now_iso()}] Already downloaded (flagged): {already_downloaded}")
    emit_log(logger, "info", f"[{utc_now_iso()}] To process: {len(todo)}")

    downloader = PDFDownloader(
        unpaywall_email=unpaywall_email,
        ncbi_tool=ncbi_tool,
        ncbi_email=ncbi_email,
        openalex_mailto=openalex_mailto,
        openalex_api_key=openalex_api_key,
        temp_dir=temp_dir,
    )

    processed = 0
    success_count = already_downloaded
    save_interval = max(1, progress_every)

    def submit_next(
        executor: ThreadPoolExecutor,
        iterator,
        in_flight: dict[Future, int],
    ) -> None:
        while len(in_flight) < max_workers * 8:
            try:
                idx = next(iterator)
            except StopIteration:
                return
            record = dataframe.iloc[idx].to_dict()
            future = executor.submit(
                process_record,
                idx,
                record,
                downloader,
                pdf_dir,
                total,
                success_count,
            )
            in_flight[future] = idx

    emit_log(logger, "info", f"[{utc_now_iso()}] Starting downloads with {max_workers} workers")

    todo_iter = iter(todo)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        in_flight: dict[Future, int] = {}
        submit_next(executor, todo_iter, in_flight)

        while in_flight:
            for future in as_completed(list(in_flight.keys()), timeout=None):
                idx = in_flight.pop(future)
                try:
                    record = future.result()
                    for key, value in record.items():
                        if key in dataframe.columns:
                            dataframe.at[idx, key] = value
                    if record.get("downloaded") is True:
                        success_count += 1
                except Exception as exc:
                    dataframe.at[idx, "downloaded"] = False
                    dataframe.at[idx, "download_error"] = f"Processing error: {exc}"

                processed += 1
                if processed % save_interval == 0:
                    write_progress(dataframe, progress_path)
                    emit_log(
                        logger,
                        "info",
                        f"[{utc_now_iso()}] Progress: [{processed}/{len(todo)}] (success: {success_count})",
                    )

                submit_next(executor, todo_iter, in_flight)
                if not in_flight:
                    break

    write_progress(dataframe, progress_path)
    return dataframe
