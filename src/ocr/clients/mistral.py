# src/ocr/clients/mistral.py
from __future__ import annotations

import base64
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

try:
    from mistralai import Mistral
except ImportError:  # Compatibility with older mistralai SDK layout.
    from mistralai.client import Mistral

from src.ocr.common import (
    ensure_ocr_columns,
    load_ocr_input_dataframe,
    persist_ocr_output,
    resolve_pdf_path,
)
from src.screening.common import emit_log, save_csv


MODEL_DEFAULT = "mistral-ocr-2512"
MAX_WORKERS = 10
MAX_RETRIES = 10
GENERIC_IMAGE_TARGET_RE = re.compile(
    r"^(?:\./)?img-(\d+)\.(?:jpe?g|png|gif|webp)$",
    re.IGNORECASE,
)


def _get_model_name(config) -> str:
    name = getattr(config, "ocr_model_name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return MODEL_DEFAULT


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _embed_tables_in_markdown(markdown_text: str, table_map: dict) -> str:
    pages = markdown_text.split("\n---\n")
    processed_pages = []

    for page_idx, page_content in enumerate(pages):
        table_refs = list(
            re.finditer(r"\[tbl-\d+\.html\]\(tbl-\d+\.html\)", page_content)
        )
        new_page_content = page_content
        offset = 0

        for local_idx, match_obj in enumerate(table_refs):
            table_key = (page_idx, local_idx)
            if table_key not in table_map:
                continue
            html_content = table_map[table_key]
            start = match_obj.start() + offset
            end = match_obj.end() + offset
            new_page_content = (
                new_page_content[:start]
                + html_content
                + new_page_content[end:]
            )
            offset += len(html_content) - (match_obj.end() - match_obj.start())

        processed_pages.append(new_page_content)

    return "\n---\n".join(processed_pages)


def _resolve_mistral_image_target(target: str, image_relpaths: list[str]) -> str | None:
    match = GENERIC_IMAGE_TARGET_RE.match(target.strip())
    if not match:
        return None
    image_index = int(match.group(1))
    if image_index >= len(image_relpaths):
        return None
    return image_relpaths[image_index]


def _rewrite_mistral_image_links(markdown_text: str, image_relpaths: list[str]) -> str:
    if not image_relpaths or not markdown_text:
        return markdown_text

    def replace_markdown_link(match_obj: re.Match[str]) -> str:
        alt_text = match_obj.group(1)
        target = match_obj.group(2)
        resolved_target = _resolve_mistral_image_target(target, image_relpaths)
        if resolved_target is None:
            return match_obj.group(0)
        return f"![{alt_text}]({resolved_target})"

    def replace_html_img(match_obj: re.Match[str]) -> str:
        prefix = match_obj.group(1)
        target = match_obj.group(2)
        suffix = match_obj.group(3)
        resolved_target = _resolve_mistral_image_target(target, image_relpaths)
        if resolved_target is None:
            return match_obj.group(0)
        return f"{prefix}{resolved_target}{suffix}"

    markdown_text = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        replace_markdown_link,
        markdown_text,
    )
    markdown_text = re.sub(
        r'(<img\b[^>]*?\bsrc=["\'])([^"\']+)(["\'])',
        replace_html_img,
        markdown_text,
        flags=re.IGNORECASE,
    )
    return markdown_text


def process_pdf(
    client: Mistral,
    pdf_path: Path,
    markdown_dir: Path,
    model_name: str,
    skip_existing: bool = True,
) -> dict:
    started = time.perf_counter()
    pdf_stem = pdf_path.stem
    md_file = markdown_dir / f"{pdf_stem}.md"
    output_dir = markdown_dir / pdf_stem

    if skip_existing and md_file.exists():
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        return {
            "pdf_id": pdf_stem,
            "status": "skipped",
            "reason": "already processed",
            "full_markdown": content,
            "markdown_file": str(md_file.resolve()),
            "num_pages": content.count("\n\n---\n\n") + (1 if content else 0),
            "elapsed_seconds": time.perf_counter() - started,
        }

    with pdf_path.open("rb") as handle:
        pdf_base64 = base64.standard_b64encode(handle.read()).decode("utf-8")

    ocr_response = None
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            ocr_response = client.ocr.process(
                model=model_name,
                document={
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{pdf_base64}",
                },
                table_format="html",
                include_image_base64=True,
            )
            break
        except Exception as exc:
            is_rate_limit = (
                getattr(exc, "status_code", None) == 429
                or "429" in str(exc)
                or "rate limit" in str(exc).lower()
                or "too many requests" in str(exc).lower()
            )
            if not is_rate_limit:
                return {
                    "pdf_id": pdf_stem,
                    "status": "error",
                    "error": str(exc),
                    "elapsed_seconds": time.perf_counter() - started,
                }
            last_err = exc
            time.sleep(random.uniform(1, 4))

    if ocr_response is None:
        return {
            "pdf_id": pdf_stem,
            "status": "error",
            "error": str(last_err) if last_err else "unknown error",
            "elapsed_seconds": time.perf_counter() - started,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    images_dir = output_dir / "images"
    tables_dir.mkdir(exist_ok=True)
    images_dir.mkdir(exist_ok=True)

    table_count = 0
    image_count = 0
    table_map = {}
    image_relpaths: list[str] = []

    for page in ocr_response.pages:
        page_idx = page.index if hasattr(page, "index") else 0

        if page.tables:
            for tbl_idx, table in enumerate(page.tables):
                table_content = getattr(table, "content", "")
                if not table_content:
                    continue
                table_file = tables_dir / f"page{page_idx}_table{tbl_idx}.html"
                table_file.write_text(table_content, encoding="utf-8")
                table_map[(page_idx, tbl_idx)] = table_content
                table_count += 1

        if page.images:
            for img_idx, image in enumerate(page.images):
                image_b64 = getattr(image, "image_base64", None)
                if not image_b64:
                    continue

                ext = "png"
                if image_b64.startswith("data:"):
                    header, image_b64 = image_b64.split(",", 1)
                    header = header.lower()
                    if "jpeg" in header or "jpg" in header:
                        ext = "jpg"
                    elif "gif" in header:
                        ext = "gif"
                    elif "webp" in header:
                        ext = "webp"
                elif image_b64.startswith("/9j/"):
                    ext = "jpg"
                elif image_b64.startswith("R0lGOD"):
                    ext = "gif"
                elif image_b64.startswith("UklGR"):
                    ext = "webp"

                image_file = images_dir / f"page{page_idx}_img{img_idx}.{ext}"
                image_file.write_bytes(base64.b64decode(image_b64))
                image_relpaths.append(
                    (Path(pdf_stem) / "images" / image_file.name).as_posix()
                )
                image_count += 1

    markdown_parts = []
    for page in ocr_response.pages:
        page_markdown = page.markdown or ""
        if page.header:
            page_markdown = (
                f"<!-- HEADER -->\n{page.header}\n<!-- /HEADER -->\n\n{page_markdown}"
            )
        if page.footer:
            page_markdown = (
                f"{page_markdown}\n\n<!-- FOOTER -->\n{page.footer}\n<!-- /FOOTER -->"
            )
        markdown_parts.append(page_markdown)

    full_markdown = "\n\n---\n\n".join(markdown_parts)
    full_markdown_with_tables = _embed_tables_in_markdown(full_markdown, table_map)
    full_markdown_with_assets = _rewrite_mistral_image_links(
        full_markdown_with_tables,
        image_relpaths,
    )
    md_file.write_text(full_markdown_with_assets, encoding="utf-8")

    metadata = {
        "source_file": str(pdf_path),
        "pdf_stem": pdf_stem,
        "markdown_file": str(md_file.resolve()),
        "output_dir": str(output_dir.resolve()),
        "num_pages": len(ocr_response.pages),
        "num_tables": table_count,
        "num_images": image_count,
        "model": getattr(ocr_response, "model", model_name),
        "markdown_image_paths": image_relpaths,
        "usage_info": (
            ocr_response.usage_info.model_dump()
            if getattr(ocr_response, "usage_info", None)
            else None
        ),
        "pages": [],
    }

    for page in ocr_response.pages:
        metadata["pages"].append(
            {
                "page_index": page.index if hasattr(page, "index") else 0,
                "dimensions": (
                    page.dimensions.model_dump()
                    if getattr(page, "dimensions", None)
                    else None
                ),
                "num_images": len(page.images) if page.images else 0,
                "num_tables": len(page.tables) if page.tables else 0,
                "num_hyperlinks": len(page.hyperlinks) if page.hyperlinks else 0,
                "has_header": bool(page.header),
                "has_footer": bool(page.footer),
            }
        )

    with (output_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    return {
        "pdf_id": pdf_stem,
        "status": "success",
        "num_pages": len(ocr_response.pages),
        "num_tables": table_count,
        "num_images": image_count,
        "full_markdown": full_markdown_with_assets,
        "markdown_file": str(md_file.resolve()),
        "elapsed_seconds": time.perf_counter() - started,
    }


def run_ocr(config, logger=None) -> int:
    api_key = getattr(config, "mistral_api_key", None)
    if not api_key:
        raise RuntimeError(
            "No Mistral API key available. Pass --mistral-api-key or set MISTRAL_API_KEY."
        )

    model_name = _get_model_name(config)
    client = Mistral(api_key=api_key)

    input_path, dataframe, pdf_path_column = load_ocr_input_dataframe(config, logger)
    dataframe = ensure_ocr_columns(dataframe, "mistral", model_name)

    markdown_dir = Path(config.ocr_markdown_dir)
    markdown_dir.mkdir(parents=True, exist_ok=True)

    tasks = []
    for idx, row in dataframe.iterrows():
        pdf_path = resolve_pdf_path(row[pdf_path_column], config, input_path)
        if not pdf_path.exists():
            dataframe.at[idx, "ocr_status"] = "error"
            dataframe.at[idx, "ocr_error"] = f"PDF not found: {pdf_path}"
            dataframe.at[idx, "ocr_processed_at"] = _utc_now_iso()
            continue
        tasks.append((idx, pdf_path))

    emit_log(logger, "info", f"Running Mistral OCR on {len(tasks)} PDFs")
    emit_log(logger, "info", f"OCR markdown directory: {markdown_dir}")

    success_count = 0
    skip_count = 0
    error_count = int((dataframe["ocr_status"] == "error").sum())

    workers = min(max(1, int(config.ocr_workers)), MAX_WORKERS)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                process_pdf,
                client,
                pdf_path,
                markdown_dir,
                model_name,
                getattr(config, "ocr_skip_existing", True),
            ): (idx, pdf_path)
            for idx, pdf_path in tasks
        }

        for counter, future in enumerate(as_completed(futures), start=1):
            idx, pdf_path = futures[future]
            pdf_id = pdf_path.stem
            try:
                result = future.result()
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}

            status = result.get("status", "error")
            dataframe.at[idx, "ocr_status"] = status
            dataframe.at[idx, "ocr_model_name"] = model_name
            dataframe.at[idx, "ocr_processed_at"] = _utc_now_iso()
            dataframe.at[idx, "ocr_elapsed_seconds"] = result.get("elapsed_seconds")
            dataframe.at[idx, "ocr_num_pages"] = result.get("num_pages")

            if status in {"success", "skipped"}:
                dataframe.at[idx, "markdown_content"] = result.get("full_markdown", "")
                dataframe.at[idx, "markdown_path"] = result.get("markdown_file", "")
                dataframe.at[idx, "ocr_error"] = None
                if status == "success":
                    success_count += 1
                else:
                    skip_count += 1
                message = (
                    f"[{counter}/{len(tasks)}] {status.upper()} {pdf_id}: "
                    f"pages={result.get('num_pages', 0)}"
                )
            else:
                dataframe.at[idx, "ocr_error"] = result.get("error", "unknown error")
                error_count += 1
                message = f"[{counter}/{len(tasks)}] ERROR {pdf_id}: {dataframe.at[idx, 'ocr_error']}"

            save_csv(dataframe, config.articles_with_markdown_path)
            emit_log(logger, "info", message)

    persist_ocr_output(dataframe, config, logger)
    emit_log(
        logger,
        "info",
        (
            f"Mistral OCR complete: total={len(dataframe)} "
            f"success={success_count} skipped={skip_count} errors={error_count}"
        ),
    )
    return 0


def main() -> int:
    from args import parse_args
    from config import Config
    from utils.logger import build_logger

    config = Config(parse_args())
    logger = build_logger(config.logs_root, f"ocr_{config.ocr_client}", config.log_level)
    return run_ocr(config, logger)


if __name__ == "__main__":
    raise SystemExit(main())
