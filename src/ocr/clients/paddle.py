# src/ocr/clients/paddle.py
from __future__ import annotations

import atexit
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import logging
import multiprocessing
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from tqdm import tqdm

from src.ocr.common import (
    expand_ocr_devices,
    ensure_ocr_columns,
    load_ocr_input_dataframe,
    persist_ocr_output,
    resolve_pdf_path,
)
from src.screening.common import emit_log, save_csv


MODEL_DEFAULT = "PaddleOCR-VL-0.9B"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_mplconfigdir():
    if os.environ.get("MPLCONFIGDIR"):
        return
    mpl_dir = Path(tempfile.gettempdir()) / "matplotlib"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(mpl_dir)


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def _safe_name(text: str) -> str:
    chars = []
    for char in text:
        if char.isalnum() or char in ("-", "_", "."):
            chars.append(char)
        else:
            chars.append("_")
    return "".join(chars).strip("_") or "doc"


def _normalize_paddle_device(device: str | None) -> str | None:
    if device is None:
        return None
    normalized = str(device).strip()
    if not normalized:
        return None
    if normalized == "cuda":
        return "gpu"
    if normalized.startswith("cuda:"):
        return "gpu:" + normalized.split(":", 1)[1]
    return normalized


def _chunk_indices(indices, batch_size):
    for index in range(0, len(indices), batch_size):
        yield indices[index : index + batch_size]


def _extract_meta(result_json):
    if not isinstance(result_json, dict):
        return None, None, None
    candidates = [result_json]
    if isinstance(result_json.get("res"), dict):
        candidates.append(result_json["res"])
    input_path = None
    page_index = None
    page_count = None
    for candidate in candidates:
        if input_path is None and isinstance(candidate.get("input_path"), str):
            input_path = candidate.get("input_path")
        if page_index is None and isinstance(candidate.get("page_index"), int):
            page_index = candidate.get("page_index")
        if page_count is None and isinstance(candidate.get("page_count"), int):
            page_count = candidate.get("page_count")
    return input_path, page_index, page_count


def _write_markdown_and_images(out_dir: Path, merged_result):
    markdown_payload = getattr(merged_result, "markdown", None)
    if not isinstance(markdown_payload, dict):
        raise RuntimeError("Result markdown attribute missing or invalid")
    texts = markdown_payload.get("markdown_texts")
    if isinstance(texts, (list, tuple)):
        markdown_text = "\n\n".join(
            text for text in texts if isinstance(text, str)
        )
    elif isinstance(texts, str):
        markdown_text = texts
    else:
        markdown_text = ""

    images = markdown_payload.get("markdown_images") or {}
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "document.md"
    if isinstance(images, dict):
        items = list(images.items())
    elif isinstance(images, (list, tuple)):
        items = [(f"images/{index}.png", image) for index, image in enumerate(images)]
    else:
        items = []

    replacements = []
    for key, image in items:
        if image is None:
            continue
        rel_path = Path(key if isinstance(key, str) else f"images/{_sha1(str(key))[:10]}.png")
        if rel_path.is_absolute():
            rel_path = Path(rel_path.name)
        if rel_path.parts and rel_path.parts[0] == "imgs":
            rel_path = Path("images", *rel_path.parts[1:])
        if not rel_path.suffix:
            rel_path = rel_path.with_suffix(".png")
        image_path = out_dir / rel_path
        image_path.parent.mkdir(parents=True, exist_ok=True)
        extension = image_path.suffix.lower()
        if extension in {".jpg", ".jpeg"}:
            image_format = "JPEG"
        elif extension == ".webp":
            image_format = "WEBP"
        elif extension == ".bmp":
            image_format = "BMP"
        elif extension in {".tif", ".tiff"}:
            image_format = "TIFF"
        else:
            image_format = "PNG"
        image.save(str(image_path), format=image_format)
        if isinstance(key, str):
            replacements.append((key, rel_path.as_posix()))
            replacements.append((f"./{key}", rel_path.as_posix()))

    for source, target in replacements:
        markdown_text = markdown_text.replace(source, target)
    md_path.write_text(markdown_text, encoding="utf-8", errors="ignore")
    return str(md_path.resolve()), markdown_text


def _wait_for_openai_server(base_url: str, timeout_seconds: int = 300):
    deadline = time.time() + timeout_seconds
    models_url = base_url.rstrip("/") + "/models"
    last_error = None
    while time.time() < deadline:
        try:
            response = httpx.get(models_url, timeout=5.0)
            if response.status_code == 200:
                return
            last_error = RuntimeError(
                f"Server returned {response.status_code} for {models_url}"
            )
        except Exception as exc:
            last_error = exc
        time.sleep(2.0)
    raise RuntimeError(
        f"Timed out waiting for vLLM server at {models_url}: {last_error}"
    )


def _terminate_process(proc: subprocess.Popen):
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()


def _ensure_vllm_server(
    model_name: str,
    base_url: str,
    python_bin: str | None,
    start_server: bool,
    gpu_memory_utilization: float,
    max_num_seqs: int,
    max_num_batched_tokens: int,
    serve_script: str | None,
):
    try:
        _wait_for_openai_server(base_url, timeout_seconds=5)
        return None
    except Exception:
        if not start_server:
            raise

    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8000
    python_executable = str(Path(python_bin)) if python_bin else sys.executable
    if serve_script:
        command = [
            "bash",
            str(Path(serve_script).resolve()),
            python_executable,
            model_name,
            host,
            str(port),
            str(gpu_memory_utilization),
            str(max_num_seqs),
            str(max_num_batched_tokens),
        ]
    else:
        command = [
            python_executable,
            "-m",
            "vllm.entrypoints.cli.main",
            "serve",
            model_name,
            "--served-model-name",
            model_name,
            "--host",
            host,
            "--port",
            str(port),
            "--trust-remote-code",
            "--gpu-memory-utilization",
            str(gpu_memory_utilization),
            "--max-num-seqs",
            str(max_num_seqs),
            "--max-num-batched-tokens",
            str(max_num_batched_tokens),
            "--no-enable-prefix-caching",
            "--mm-processor-cache-gb",
            "0",
            "--disable-log-stats",
        ]
    proc = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
    )
    atexit.register(_terminate_process, proc)
    _wait_for_openai_server(base_url, timeout_seconds=300)
    return proc


def _get_model_name(config) -> str:
    if getattr(config, "ocr_model_name", None):
        return str(config.ocr_model_name).strip()
    if getattr(config, "paddle_vl_model_name", None):
        return str(config.paddle_vl_model_name).strip()
    return MODEL_DEFAULT


def _resolve_devices(config) -> list[str]:
    devices = [
        _normalize_paddle_device(device) or "cpu"
        for device in expand_ocr_devices(config.ocr_device, gpu_prefix="gpu")
    ]
    max_workers = max(1, int(config.ocr_workers))
    if config.paddle_backend != "local":
        return devices[:1]
    return devices[: min(len(devices), max_workers)]


def _build_pipeline(config, model_name: str, device: str | None = None):
    from paddleocr import PaddleOCRVL

    pipeline_kwargs = dict(
        pipeline_version=config.paddle_pipeline_version,
        vl_rec_model_name=model_name,
    )
    paddle_device = _normalize_paddle_device(device if device is not None else config.ocr_device)
    if paddle_device:
        pipeline_kwargs["device"] = paddle_device

    if config.paddle_backend == "vllm-server":
        _ensure_vllm_server(
            model_name=model_name,
            base_url=config.paddle_vllm_url,
            python_bin=config.paddle_vllm_python_bin,
            start_server=bool(config.paddle_start_vllm_server),
            gpu_memory_utilization=config.paddle_gpu_memory_utilization,
            max_num_seqs=config.paddle_max_num_seqs,
            max_num_batched_tokens=config.paddle_max_num_batched_tokens,
            serve_script=config.paddle_serve_script,
        )
        pipeline_kwargs.update(
            vl_rec_backend="vllm-server",
            vl_rec_server_url=config.paddle_vllm_url,
            vl_rec_api_model_name=model_name,
            vl_rec_max_concurrency=config.paddle_vl_rec_max_concurrency,
            use_queues=bool(config.paddle_use_queues),
            enable_hpi=bool(config.paddle_enable_hpi),
            precision=config.paddle_precision,
            use_tensorrt=bool(config.paddle_use_tensorrt),
            layout_detection_model_name="PP-DocLayoutV2",
        )
    else:
        pipeline_kwargs.update(
            vl_rec_max_concurrency=config.paddle_vl_rec_max_concurrency,
            use_queues=bool(config.paddle_use_queues),
            layout_detection_model_name="PP-DocLayoutV2",
        )

    return PaddleOCRVL(**pipeline_kwargs)


def _run_device_bucket(
    device: str,
    indices: list[int],
    resolved_paths: dict[int, Path],
    row_started_at: dict[int, float],
    config,
    model_name: str,
):
    updates: dict[int, dict] = {}
    try:
        pipeline = _build_pipeline(config, model_name, device=device)
    except Exception as exc:
        error_message = f"{device}: {exc}"
        now = time.perf_counter()
        for row_index in indices:
            updates[row_index] = {
                "ocr_status": "error",
                "ocr_error": error_message,
                "ocr_num_pages": 0,
                "ocr_elapsed_seconds": now - row_started_at[row_index],
            }
        return device, updates

    path_to_rows: dict[str, list[int]] = {}
    for row_index in indices:
        path_to_rows.setdefault(str(resolved_paths[row_index]), []).append(row_index)

    batch_indices = list(_chunk_indices(indices, config.paddle_batch_size))
    for batch in batch_indices:
        batch_paths = [str(resolved_paths[row_index]) for row_index in batch]
        groups = {}
        expected_pages = {}
        batch_updates: dict[int, dict] = {}

        try:
            output = pipeline.predict(batch_paths)
            for result in output:
                try:
                    result_json = getattr(result, "json", None)
                    input_pdf, page_index, page_count = _extract_meta(result_json)
                    if input_pdf is None:
                        input_pdf = getattr(result, "input_path", None)
                    if input_pdf is None:
                        input_pdf = "unknown"
                    groups.setdefault(input_pdf, []).append(result)
                    if page_count is not None and page_count > 0:
                        expected_pages[input_pdf] = page_count

                    is_done = bool(
                        page_count is not None
                        and page_index is not None
                        and page_count > 0
                        and int(page_index) == int(page_count) - 1
                    )
                    if (
                        not is_done
                        and expected_pages.get(input_pdf, 0) > 0
                        and len(groups[input_pdf]) >= expected_pages[input_pdf]
                    ):
                        is_done = True
                    if not is_done or input_pdf == "unknown":
                        continue

                    pages = groups.pop(input_pdf, [])
                    page_total = expected_pages.pop(input_pdf, None)
                    merged_list = list(
                        pipeline.restructure_pages(
                            pages,
                            merge_tables=True,
                            relevel_titles=True,
                            concatenate_pages=True,
                        )
                    )
                    if not merged_list:
                        raise RuntimeError("Empty restructure_pages result")
                    doc_id = (
                        f"{_safe_name(Path(input_pdf).stem)}_"
                        f"{_sha1(str(Path(input_pdf).resolve()))[:10]}"
                    )
                    markdown_path, markdown_text = _write_markdown_and_images(
                        Path(config.ocr_markdown_dir) / doc_id,
                        merged_list[0],
                    )
                    for row_index in path_to_rows.get(input_pdf, []):
                        batch_updates[row_index] = {
                            "markdown_path": markdown_path,
                            "markdown_content": markdown_text,
                            "ocr_status": "success",
                            "ocr_error": None,
                            "ocr_num_pages": page_total or len(pages),
                        }
                except Exception as exc:
                    logging.exception("Failed on Paddle page result: %s", exc)

            for input_pdf, pages in list(groups.items()):
                if input_pdf == "unknown":
                    continue
                try:
                    merged_list = list(
                        pipeline.restructure_pages(
                            pages,
                            merge_tables=True,
                            relevel_titles=True,
                            concatenate_pages=True,
                        )
                    )
                    if not merged_list:
                        raise RuntimeError("Empty restructure_pages result")
                    doc_id = (
                        f"{_safe_name(Path(input_pdf).stem)}_"
                        f"{_sha1(str(Path(input_pdf).resolve()))[:10]}"
                    )
                    markdown_path, markdown_text = _write_markdown_and_images(
                        Path(config.ocr_markdown_dir) / doc_id,
                        merged_list[0],
                    )
                    for row_index in path_to_rows.get(input_pdf, []):
                        batch_updates[row_index] = {
                            "markdown_path": markdown_path,
                            "markdown_content": markdown_text,
                            "ocr_status": "success",
                            "ocr_error": None,
                            "ocr_num_pages": len(pages),
                        }
                except Exception as exc:
                    for row_index in path_to_rows.get(input_pdf, []):
                        batch_updates[row_index] = {
                            "ocr_status": "error",
                            "ocr_error": str(exc),
                            "ocr_num_pages": 0,
                        }
        except Exception as exc:
            for pdf_path in batch_paths:
                for row_index in path_to_rows.get(pdf_path, []):
                    batch_updates[row_index] = {
                        "ocr_status": "error",
                        "ocr_error": str(exc),
                        "ocr_num_pages": 0,
                    }

        for row_index in batch:
            update = batch_updates.setdefault(row_index, {})
            status = str(update.get("ocr_status", "")).strip().lower()
            if status in {"", "nan", "none"}:
                error_value = str(update.get("ocr_error", "")).strip()
                update["ocr_status"] = "error"
                update["ocr_error"] = (
                    error_value
                    if error_value.lower() not in {"", "nan", "none"}
                    else "OCR result missing"
                )
                update.setdefault("ocr_num_pages", 0)
            update["ocr_elapsed_seconds"] = time.perf_counter() - row_started_at[row_index]

        updates.update(batch_updates)

    return device, updates


def run_ocr(config, logger=None) -> int:
    _ensure_mplconfigdir()

    model_name = _get_model_name(config)
    input_path, dataframe, pdf_path_column = load_ocr_input_dataframe(config, logger)
    dataframe = ensure_ocr_columns(dataframe, "paddle", model_name)
    markdown_root = Path(config.ocr_markdown_dir)
    markdown_root.mkdir(parents=True, exist_ok=True)

    resolved_paths = {}
    row_started_at = {}
    todo_indices = []
    for idx, row in dataframe.iterrows():
        row_started_at[idx] = time.perf_counter()
        pdf_path = resolve_pdf_path(row[pdf_path_column], config, input_path)
        resolved_paths[idx] = pdf_path
        dataframe.at[idx, "ocr_model_name"] = model_name
        dataframe.at[idx, "ocr_processed_at"] = _utc_now_iso()
        if not pdf_path.exists():
            dataframe.at[idx, "ocr_status"] = "error"
            dataframe.at[idx, "ocr_error"] = f"PDF not found: {pdf_path}"
            dataframe.at[idx, "ocr_elapsed_seconds"] = time.perf_counter() - row_started_at[idx]
            continue

        doc_id = f"{_safe_name(pdf_path.stem)}_{_sha1(str(pdf_path.resolve()))[:10]}"
        md_path = markdown_root / doc_id / "document.md"
        if config.ocr_skip_existing and md_path.exists():
            dataframe.at[idx, "markdown_path"] = str(md_path.resolve())
            dataframe.at[idx, "markdown_content"] = md_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
            dataframe.at[idx, "ocr_status"] = "skipped"
            dataframe.at[idx, "ocr_error"] = None
            dataframe.at[idx, "ocr_num_pages"] = (
                dataframe.at[idx, "markdown_content"].count("\n\n---\n\n") + 1
            )
            dataframe.at[idx, "ocr_elapsed_seconds"] = time.perf_counter() - row_started_at[idx]
            continue

        todo_indices.append(idx)

    if not todo_indices:
        persist_ocr_output(dataframe, config, logger)
        emit_log(logger, "info", "No PDFs left to OCR for Paddle.")
        return 0

    devices = _resolve_devices(config)
    active_devices = devices[: min(len(devices), len(todo_indices))]
    emit_log(
        logger,
        "info",
        (
            f"Running Paddle OCR with backend={config.paddle_backend} on {len(todo_indices)} PDFs "
            f"using {len(active_devices)} worker(s): {', '.join(active_devices)}"
        ),
    )

    buckets: list[list[int]] = [[] for _ in active_devices]
    for offset, row_index in enumerate(todo_indices):
        buckets[offset % len(active_devices)].append(row_index)

    if len(active_devices) == 1:
        device, updates = _run_device_bucket(
            active_devices[0],
            buckets[0],
            resolved_paths,
            row_started_at,
            config,
            model_name,
        )
        for row_index, update in updates.items():
            dataframe.at[row_index, "ocr_status"] = update.get("ocr_status", "error")
            dataframe.at[row_index, "ocr_error"] = update.get("ocr_error")
            dataframe.at[row_index, "ocr_num_pages"] = update.get("ocr_num_pages", 0)
            dataframe.at[row_index, "ocr_elapsed_seconds"] = update.get("ocr_elapsed_seconds")
            if update.get("ocr_status") == "success":
                dataframe.at[row_index, "markdown_path"] = update.get("markdown_path", "")
                dataframe.at[row_index, "markdown_content"] = update.get("markdown_content", "")
        save_csv(dataframe, config.articles_with_markdown_path)
        emit_log(
            logger,
            "info",
            f"Completed Paddle OCR worker on {device}: {len(updates)} PDF(s)",
        )
    else:
        mp_context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(
            max_workers=len(active_devices),
            mp_context=mp_context,
        ) as executor:
            futures = {
                executor.submit(
                    _run_device_bucket,
                    device,
                    bucket,
                    resolved_paths,
                    row_started_at,
                    config,
                    model_name,
                ): device
                for device, bucket in zip(active_devices, buckets)
                if bucket
            }
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="OCR (Paddle workers)",
                unit="worker",
            ):
                device, updates = future.result()
                for row_index, update in updates.items():
                    dataframe.at[row_index, "ocr_status"] = update.get("ocr_status", "error")
                    dataframe.at[row_index, "ocr_error"] = update.get("ocr_error")
                    dataframe.at[row_index, "ocr_num_pages"] = update.get("ocr_num_pages", 0)
                    dataframe.at[row_index, "ocr_elapsed_seconds"] = update.get("ocr_elapsed_seconds")
                    if update.get("ocr_status") == "success":
                        dataframe.at[row_index, "markdown_path"] = update.get("markdown_path", "")
                        dataframe.at[row_index, "markdown_content"] = update.get("markdown_content", "")

                save_csv(dataframe, config.articles_with_markdown_path)
                emit_log(
                    logger,
                    "info",
                    f"Completed Paddle OCR worker on {device}: {len(updates)} PDF(s)",
                )

    retry_indices = [
        row_index
        for row_index in todo_indices
        if str(dataframe.at[row_index, "ocr_status"]).strip().lower() == "error"
    ]
    if retry_indices and len(active_devices) > 1 and config.paddle_backend == "local":
        emit_log(
            logger,
            "warning",
            (
                f"Retrying {len(retry_indices)} Paddle OCR error(s) serially on "
                f"{active_devices[0]}"
            ),
        )
        retry_started_at = {
            row_index: time.perf_counter()
            for row_index in retry_indices
        }
        _, retry_updates = _run_device_bucket(
            active_devices[0],
            retry_indices,
            resolved_paths,
            retry_started_at,
            config,
            model_name,
        )
        for row_index, update in retry_updates.items():
            dataframe.at[row_index, "ocr_status"] = update.get("ocr_status", "error")
            dataframe.at[row_index, "ocr_error"] = update.get("ocr_error")
            dataframe.at[row_index, "ocr_num_pages"] = update.get("ocr_num_pages", 0)
            dataframe.at[row_index, "ocr_elapsed_seconds"] = update.get("ocr_elapsed_seconds")
            if update.get("ocr_status") == "success":
                dataframe.at[row_index, "markdown_path"] = update.get("markdown_path", "")
                dataframe.at[row_index, "markdown_content"] = update.get("markdown_content", "")
        save_csv(dataframe, config.articles_with_markdown_path)

    persist_ocr_output(dataframe, config, logger)
    emit_log(
        logger,
        "info",
        (
            "Paddle OCR complete: "
            f"{dataframe['ocr_status'].fillna('').value_counts().to_dict()}"
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
