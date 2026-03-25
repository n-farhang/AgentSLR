# src/harvest/fetch_metadata.py

from __future__ import annotations

import re
import sys
from typing import Any

from lxml import etree
import requests

from src.harvest.common import (
    RateLimiter,
    build_dedupe_key,
    can_merge,
    emit_log,
    generate_article_id,
    merge_records,
    normalize_doi,
    normalize_pmcid,
    normalize_pmid,
    utc_now_iso,
)


def openalex_inverted_index_to_abstract(
    inverted_index: dict[str, list[int]] | None,
) -> str | None:
    if not inverted_index:
        return None

    max_position = -1
    for positions in inverted_index.values():
        if positions:
            max_position = max(max_position, max(positions))

    if max_position < 0:
        return None

    words = [""] * (max_position + 1)
    for word, positions in inverted_index.items():
        for position in positions:
            if 0 <= position <= max_position:
                words[position] = word

    abstract = " ".join(word for word in words if word).strip()
    return abstract or None


def extract_openalex_ids(ids_obj: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not ids_obj:
        return None, None

    pmid = ids_obj.get("pmid")
    pmcid = ids_obj.get("pmcid")

    def pull_digits(value: Any) -> str | None:
        if not value:
            return None
        match = re.search(r"(\d+)", str(value))
        return match.group(1) if match else None

    def pull_pmc(value: Any) -> str | None:
        if not value:
            return None
        match = re.search(r"(PMC\d+)", str(value), re.IGNORECASE)
        return match.group(1).upper() if match else None

    return pull_digits(pmid), pull_pmc(pmcid)


def openalex_work_to_record(
    work: dict[str, Any],
    pathogen: str,
    query: str,
    harvested_at: str,
) -> dict[str, Any]:
    ids_obj = work.get("ids") or {}
    pmid, pmcid = extract_openalex_ids(ids_obj)
    title = work.get("title") or work.get("display_name")
    doi = work.get("doi")
    year = work.get("publication_year")
    abstract = openalex_inverted_index_to_abstract(work.get("abstract_inverted_index"))

    authors = []
    for authorship in work.get("authorships") or []:
        author_name = (authorship.get("author") or {}).get("display_name")
        if author_name:
            authors.append(author_name)

    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    journal = source.get("display_name")
    best_location = work.get("best_oa_location") or {}
    openalex_pdf_url = best_location.get("url_for_pdf") or None
    openalex_id = work.get("id")

    if pmid:
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    else:
        url = primary_location.get("landing_page_url") or openalex_id or doi

    return {
        "source": "OpenAlex",
        "pmid": pmid,
        "pmcid": pmcid,
        "doi": normalize_doi(doi),
        "title": title,
        "authors": "; ".join(authors) if authors else None,
        "journal": journal,
        "year": int(year) if isinstance(year, int) else year,
        "abstract": abstract,
        "url": url,
        "openalex_id": openalex_id,
        "openalex_pdf_url": openalex_pdf_url,
        "pathogen": pathogen,
        "query": query,
        "harvested_at": harvested_at,
    }


def openalex_iter_search(
    session: requests.Session,
    limiter: RateLimiter,
    query: str,
    mailto: str | None,
    api_key: str | None,
    max_records: int,
    per_page: int,
):
    cursor = "*"
    fetched = 0
    base_url = "https://api.openalex.org/works"
    select_fields = (
        "id,doi,title,publication_year,authorships,primary_location,"
        "best_oa_location,ids,abstract_inverted_index"
    )
    headers = {"User-Agent": f"AgentSLR (mailto:{mailto})" if mailto else "AgentSLR"}

    while cursor and fetched < max_records:
        params: dict[str, Any] = {
            "search": query,
            "per-page": per_page,
            "cursor": cursor,
            "select": select_fields,
        }
        if mailto:
            params["mailto"] = mailto
        if api_key:
            params["api_key"] = api_key

        limiter.wait()
        response = session.get(base_url, params=params, timeout=(5, 15), headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"OpenAlex HTTP {response.status_code}: {response.text[:400]}")

        data = response.json()
        results = data.get("results") or []
        for work in results:
            yield work
            fetched += 1
            if fetched >= max_records:
                break

        cursor = (data.get("meta") or {}).get("next_cursor")
        if not results:
            break


def pubmed_esearch_history(
    session: requests.Session,
    limiter: RateLimiter,
    term: str,
    api_key: str | None,
    email: str | None,
    tool: str,
    sort: str | None,
) -> tuple[int, str, str]:
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params: dict[str, Any] = {
        "db": "pubmed",
        "term": term,
        "retmode": "json",
        "usehistory": "y",
        "tool": tool,
    }
    if sort:
        params["sort"] = sort
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key

    limiter.wait()
    response = session.get(url, params=params, timeout=(5, 15))
    if response.status_code >= 400:
        raise RuntimeError(f"PubMed esearch HTTP {response.status_code}: {response.text[:400]}")

    result = response.json().get("esearchresult") or {}
    count = int(result.get("count") or 0)
    webenv = result.get("webenv")
    querykey = result.get("querykey")
    if not webenv or not querykey:
        raise RuntimeError("PubMed esearch did not return WebEnv/querykey")
    return count, webenv, querykey


def etree_text(node: etree._Element | None) -> str | None:
    if node is None:
        return None
    text = "".join(node.itertext()).strip()
    return text or None


def parse_pubmed_year(pubdate: etree._Element | None) -> int | None:
    if pubdate is None:
        return None

    year = etree_text(pubdate.find("Year"))
    if year and re.match(r"^\d{4}$", year):
        return int(year)

    medline_date = etree_text(pubdate.find("MedlineDate"))
    if medline_date:
        match = re.search(r"(\d{4})", medline_date)
        if match:
            return int(match.group(1))

    return None


def parse_pubmed_article(article: etree._Element) -> dict[str, Any]:
    pmid = etree_text(article.find(".//PMID"))
    title = etree_text(article.find(".//ArticleTitle"))

    abstract_parts = []
    for node in article.findall(".//Abstract/AbstractText"):
        label = node.get("Label")
        text = etree_text(node)
        if text:
            abstract_parts.append(f"{label}: {text}" if label else text)

    authors = []
    for author in article.findall(".//AuthorList/Author"):
        collective = etree_text(author.find("CollectiveName"))
        if collective:
            authors.append(collective)
            continue

        last = etree_text(author.find("LastName"))
        fore = etree_text(author.find("ForeName"))
        if last and fore:
            authors.append(f"{last}, {fore}")
        elif last:
            authors.append(last)

    journal = etree_text(article.find(".//Journal/Title"))
    year = parse_pubmed_year(article.find(".//JournalIssue/PubDate"))

    doi = None
    pmcid = None
    for identifier in article.findall(".//ArticleIdList/ArticleId"):
        identifier_type = identifier.get("IdType")
        value = etree_text(identifier)
        if not value or not identifier_type:
            continue
        if identifier_type.lower() == "doi":
            doi = value
        if identifier_type.lower() in ("pmc", "pmcid"):
            pmcid = value.upper() if value.upper().startswith("PMC") else f"PMC{value}"

    return {
        "pmid": pmid,
        "pmcid": pmcid,
        "doi": normalize_doi(doi),
        "title": title,
        "authors": "; ".join(authors) if authors else None,
        "journal": journal,
        "year": year,
        "abstract": "\n".join(abstract_parts).strip() if abstract_parts else None,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
    }


def pubmed_efetch_batches(
    session: requests.Session,
    limiter: RateLimiter,
    webenv: str,
    querykey: str,
    total: int,
    max_records: int,
    batch_size: int,
    api_key: str | None,
    email: str | None,
    tool: str,
):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    take = min(total, max_records)

    for start in range(0, take, batch_size):
        params: dict[str, Any] = {
            "db": "pubmed",
            "query_key": querykey,
            "WebEnv": webenv,
            "retstart": start,
            "retmax": min(batch_size, take - start),
            "retmode": "xml",
            "tool": tool,
        }
        if email:
            params["email"] = email
        if api_key:
            params["api_key"] = api_key

        limiter.wait()
        response = session.get(url, params=params, timeout=(10, 30))
        if response.status_code >= 400:
            raise RuntimeError(f"PubMed efetch HTTP {response.status_code}: {response.text[:400]}")

        root = etree.fromstring(response.content)
        for article in root.findall(".//PubmedArticle"):
            yield parse_pubmed_article(article)


def europepmc_pick_pdf_url(full_text_urls: Any) -> str | None:
    if not full_text_urls:
        return None

    items = full_text_urls.get("fullTextUrl") if isinstance(full_text_urls, dict) else None
    if not items:
        return None
    if isinstance(items, dict):
        items = [items]

    best = None
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        document_format = str(item.get("documentFormat") or "").lower()
        document_style = str(item.get("documentStyle") or "").lower()
        availability = str(item.get("availability") or "").lower()
        if not url:
            continue
        if "pdf" in document_format or "pdf" in document_style or str(url).lower().endswith(".pdf"):
            if availability in ("free", "open access", "oa", ""):
                return url
            best = best or url

    return best


def europepmc_result_to_record(
    result: dict[str, Any],
    pathogen: str,
    query: str,
    harvested_at: str,
) -> dict[str, Any]:
    pmid = result.get("pmid") or result.get("id")
    pmcid = result.get("pmcid")
    doi = result.get("doi")
    title = result.get("title")
    authors = result.get("authorString")
    journal = result.get("journalTitle")
    year = result.get("pubYear")
    abstract = result.get("abstractText")

    if pmid and str(result.get("source") or "").upper() == "MED":
        url = f"https://pubmed.ncbi.nlm.nih.gov/{normalize_pmid(str(pmid))}/"
    else:
        url = result.get("url")

    return {
        "source": "EuropePMC",
        "pmid": normalize_pmid(str(pmid)) if pmid else None,
        "pmcid": normalize_pmcid(str(pmcid)) if pmcid else None,
        "doi": normalize_doi(doi),
        "title": title,
        "authors": authors,
        "journal": journal,
        "year": int(year) if isinstance(year, str) and year.isdigit() else year,
        "abstract": abstract,
        "url": url,
        "openalex_id": None,
        "openalex_pdf_url": europepmc_pick_pdf_url(result.get("fullTextUrlList")),
        "pathogen": pathogen,
        "query": query,
        "harvested_at": harvested_at,
    }


def europepmc_iter_search(
    session: requests.Session,
    limiter: RateLimiter,
    query: str,
    max_records: int,
    page_size: int,
    synonym: str,
    sort: str | None,
):
    base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    cursor = "*"
    fetched = 0

    while fetched < max_records and cursor:
        params: dict[str, Any] = {
            "query": query,
            "format": "json",
            "resultType": "core",
            "pageSize": page_size,
            "cursorMark": cursor,
            "synonym": synonym,
        }
        if sort:
            params["sort"] = sort

        limiter.wait()
        response = session.get(base_url, params=params, timeout=(10, 30))
        if response.status_code >= 400:
            raise RuntimeError(f"EuropePMC HTTP {response.status_code}: {response.text[:400]}")

        data = response.json()
        results = ((data.get("resultList") or {}).get("result")) or []
        if isinstance(results, dict):
            results = [results]

        for result in results:
            yield result
            fetched += 1
            if fetched >= max_records:
                break

        next_cursor = data.get("nextCursorMark") or data.get("next_cursor_mark")
        if not results or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor


def harvest_metadata(
    pathogen: str,
    session: requests.Session,
    oa_limiter: RateLimiter,
    ncbi_limiter: RateLimiter,
    epmc_limiter: RateLimiter,
    config: Any,
    logger: Any = None,
) -> list[dict[str, Any]]:
    harvested_at = utc_now_iso()
    dedupe: dict[tuple[Any, ...], dict[str, Any]] = {}

    emit_log(logger, "info", f"[{harvested_at}] Harvest start: {pathogen}")

    try:
        openalex_count = 0
        for work in openalex_iter_search(
            session=session,
            limiter=oa_limiter,
            query=config.openalex_query,
            mailto=config.openalex_mailto,
            api_key=config.openalex_api_key,
            max_records=config.openalex_max,
            per_page=config.openalex_per_page,
        ):
            record = openalex_work_to_record(work, pathogen, config.openalex_query, harvested_at)
            key = build_dedupe_key(record)
            dedupe[key] = merge_records(dedupe[key], record) if key in dedupe else record
            openalex_count += 1
            if openalex_count % 500 == 0:
                emit_log(logger, "info", f"[{utc_now_iso()}] OpenAlex harvested: {openalex_count}")
        emit_log(logger, "info", f"[{utc_now_iso()}] OpenAlex harvested total: {openalex_count}")
    except Exception as exc:
        emit_log(logger, "error", f"[{utc_now_iso()}] OpenAlex error: {exc}")

    try:
        total, webenv, querykey = pubmed_esearch_history(
            session=session,
            limiter=ncbi_limiter,
            term=config.pubmed_query,
            api_key=config.ncbi_api_key,
            email=config.ncbi_email,
            tool=config.ncbi_tool,
            sort=config.pubmed_sort,
        )
        pubmed_count = 0
        for item in pubmed_efetch_batches(
            session=session,
            limiter=ncbi_limiter,
            webenv=webenv,
            querykey=querykey,
            total=total,
            max_records=config.pubmed_max,
            batch_size=config.pubmed_batch,
            api_key=config.ncbi_api_key,
            email=config.ncbi_email,
            tool=config.ncbi_tool,
        ):
            record = {
                "source": "PubMed",
                "pmid": item.get("pmid"),
                "pmcid": item.get("pmcid"),
                "doi": item.get("doi"),
                "title": item.get("title"),
                "authors": item.get("authors"),
                "journal": item.get("journal"),
                "year": item.get("year"),
                "abstract": item.get("abstract"),
                "url": item.get("url"),
                "openalex_id": None,
                "openalex_pdf_url": None,
                "pathogen": pathogen,
                "query": config.pubmed_query,
                "harvested_at": harvested_at,
            }
            key = build_dedupe_key(record)
            dedupe[key] = merge_records(dedupe[key], record) if key in dedupe else record
            pubmed_count += 1
            if pubmed_count % 500 == 0:
                emit_log(logger, "info", f"[{utc_now_iso()}] PubMed harvested: {pubmed_count}")
        emit_log(logger, "info", f"[{utc_now_iso()}] PubMed harvested total: {pubmed_count}")
    except Exception as exc:
        emit_log(logger, "error", f"[{utc_now_iso()}] PubMed error: {exc}")

    if config.use_europepmc:
        try:
            europepmc_count = 0
            for result in europepmc_iter_search(
                session=session,
                limiter=epmc_limiter,
                query=config.europepmc_query,
                max_records=config.europepmc_max,
                page_size=config.europepmc_page,
                synonym=config.europepmc_synonym,
                sort=config.europepmc_sort,
            ):
                record = europepmc_result_to_record(
                    result,
                    pathogen,
                    config.europepmc_query,
                    harvested_at,
                )
                key = build_dedupe_key(record)
                dedupe[key] = merge_records(dedupe[key], record) if key in dedupe else record
                europepmc_count += 1
                if europepmc_count % 500 == 0:
                    emit_log(
                        logger,
                        "info",
                        f"[{utc_now_iso()}] EuropePMC harvested: {europepmc_count}",
                    )
            emit_log(
                logger,
                "info",
                f"[{utc_now_iso()}] EuropePMC harvested total: {europepmc_count}",
            )
        except Exception as exc:
            emit_log(logger, "error", f"[{utc_now_iso()}] EuropePMC error: {exc}")

    records = list(dedupe.values())
    for record in records:
        record["article_id"] = generate_article_id(record)
    return records
