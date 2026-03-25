# src/ocr/clients/glm.py
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from tqdm import tqdm
from transformers import AutoModelForImageTextToText, AutoProcessor

from src.ocr.clients.ocr_common import (
    doc_output_dir,
    extract_pdf_images_by_page,
    render_pdf_pages_to_pil,
    write_markdown,
)
from src.ocr.common import (
    expand_ocr_devices,
    ensure_ocr_columns,
    load_ocr_input_dataframe,
    persist_ocr_output,
    resolve_pdf_path,
)
from src.screening.common import emit_log, save_csv


MODEL_DEFAULT = "zai-org/GLM-OCR"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GLMOCRClient:
    def __init__(
        self,
        model_name: str,
        device: str,
        dtype: str,
        max_new_tokens: int,
        page_batch_size: int,
    ):
        if device.startswith("cuda") and dtype == "bfloat16":
            torch_dtype = torch.bfloat16
        elif device.startswith("cuda"):
            torch_dtype = torch.float16
        else:
            torch_dtype = torch.float32

        self.processor = AutoProcessor.from_pretrained(
            model_name,
            trust_remote_code=True,
        )
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype=torch_dtype,
        ).to(device)
        self.model.eval()
        self.max_new_tokens = max_new_tokens
        self.page_batch_size = max(1, page_batch_size)
        self.prompt = "Text Recognition:"

    def ocr_batch(self, images) -> list[str]:
        texts = []
        for _ in images:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": self.prompt},
                    ],
                }
            ]
            texts.append(
                self.processor.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            )
        inputs = self.processor(
            text=texts,
            images=images,
            padding=True,
            return_tensors="pt",
        )
        inputs = {key: value.to(self.model.device) for key, value in inputs.items()}
        inputs.pop("token_type_ids", None)
        prompt_length = inputs["input_ids"].shape[1]
        with torch.inference_mode():
            generated = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )
        decoded = self.processor.batch_decode(
            generated[:, prompt_length:],
            skip_special_tokens=True,
        )
        return [text.strip() for text in decoded]

    def ocr_pdf(self, pdf_path: str, pdf_scale: float) -> tuple[list[str], int]:
        page_images = render_pdf_pages_to_pil(pdf_path, pdf_scale)
        outputs = []
        try:
            for index in range(0, len(page_images), self.page_batch_size):
                batch_images = page_images[index : index + self.page_batch_size]
                outputs.extend(self.ocr_batch(batch_images))
        finally:
            for image in page_images:
                image.close()
        return outputs, len(page_images)


def _resolve_devices(config) -> list[str]:
    devices = expand_ocr_devices(config.ocr_device, gpu_prefix="cuda")
    max_workers = max(1, int(config.ocr_workers))
    return devices[: min(len(devices), max_workers)]


def _process_pdf(client: GLMOCRClient, pdf_path: Path, out_dir: Path, pdf_scale: float) -> dict:
    page_chunks, num_pages = client.ocr_pdf(
        str(pdf_path),
        pdf_scale,
    )
    images_by_page = extract_pdf_images_by_page(str(pdf_path), out_dir / "images")
    merged_pages = []
    for page_index, page_text in enumerate(page_chunks, start=1):
        chunk = page_text.strip()
        page_images = images_by_page.get(page_index, [])
        if page_images:
            image_block = "\n\n".join(
                f"![](images/{name})" for name in page_images
            )
            chunk = f"{chunk}\n\n{image_block}" if chunk else image_block
        merged_pages.append(chunk)

    markdown_text = "\n\n---\n\n".join(merged_pages)
    saved_md_path = write_markdown(out_dir, markdown_text)
    return {
        "markdown_path": saved_md_path,
        "markdown_content": markdown_text,
        "ocr_status": "success",
        "ocr_error": None,
        "ocr_num_pages": num_pages,
    }


def _run_device_bucket(device: str, tasks: list[tuple[int, Path, Path]], config, model_name: str):
    results: list[tuple[int, dict]] = []
    try:
        client = GLMOCRClient(
            model_name=model_name,
            device=device,
            dtype=config.ocr_dtype,
            max_new_tokens=config.ocr_max_new_tokens,
            page_batch_size=config.ocr_page_batch_size,
        )
    except Exception as exc:
        error_message = f"{device}: {exc}"
        for idx, _, _ in tasks:
            results.append(
                (
                    idx,
                    {
                        "ocr_status": "error",
                        "ocr_error": error_message,
                        "ocr_num_pages": 0,
                    },
                )
            )
        return device, results

    for idx, pdf_path, out_dir in tasks:
        started = time.perf_counter()
        try:
            result = _process_pdf(client, pdf_path, out_dir, config.ocr_pdf_scale)
        except Exception as exc:
            result = {
                "ocr_status": "error",
                "ocr_error": str(exc),
                "ocr_num_pages": 0,
            }
        result["ocr_elapsed_seconds"] = time.perf_counter() - started
        results.append((idx, result))
    return device, results


def _get_model_name(config) -> str:
    if getattr(config, "ocr_model_name", None):
        return str(config.ocr_model_name).strip()
    return MODEL_DEFAULT


def run_ocr(config, logger=None) -> int:
    model_name = _get_model_name(config)
    input_path, dataframe, pdf_path_column = load_ocr_input_dataframe(config, logger)
    dataframe = ensure_ocr_columns(dataframe, "glm", model_name)

    emit_log(logger, "info", f"Preparing GLM OCR for {len(dataframe)} PDFs")
    emit_log(logger, "info", f"OCR markdown directory: {config.ocr_markdown_dir}")

    todo_tasks: list[tuple[int, Path, Path]] = []
    for idx, row in tqdm(
        dataframe.iterrows(),
        total=len(dataframe),
        desc="Prepare OCR (GLM)",
        unit="pdf",
    ):
        started = time.perf_counter()
        pdf_path = resolve_pdf_path(row[pdf_path_column], config, input_path)
        dataframe.at[idx, "ocr_model_name"] = model_name
        dataframe.at[idx, "ocr_processed_at"] = _utc_now_iso()

        if not pdf_path.exists():
            dataframe.at[idx, "ocr_status"] = "error"
            dataframe.at[idx, "ocr_error"] = f"PDF not found: {pdf_path}"
            dataframe.at[idx, "ocr_num_pages"] = 0
            dataframe.at[idx, "ocr_elapsed_seconds"] = time.perf_counter() - started
            continue

        out_dir = doc_output_dir(config.ocr_markdown_dir, str(pdf_path.resolve()))
        md_path = out_dir / "document.md"
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
            dataframe.at[idx, "ocr_elapsed_seconds"] = time.perf_counter() - started
            continue

        todo_tasks.append((idx, pdf_path, out_dir))

    if not todo_tasks:
        persist_ocr_output(dataframe, config, logger)
        emit_log(logger, "info", "No PDFs left to OCR for GLM.")
        return 0

    devices = _resolve_devices(config)
    active_devices = devices[: min(len(devices), len(todo_tasks))]
    emit_log(
        logger,
        "info",
        (
            f"Running GLM OCR on {len(todo_tasks)} PDFs with {len(active_devices)} "
            f"worker(s): {', '.join(active_devices)}"
        ),
    )

    buckets: list[list[tuple[int, Path, Path]]] = [[] for _ in active_devices]
    for offset, task in enumerate(todo_tasks):
        buckets[offset % len(active_devices)].append(task)

    with ThreadPoolExecutor(max_workers=len(active_devices)) as executor:
        futures = {
            executor.submit(_run_device_bucket, device, bucket, config, model_name): device
            for device, bucket in zip(active_devices, buckets)
            if bucket
        }
        for future in tqdm(
            as_completed(futures),
            total=len(futures),
            desc="OCR (GLM workers)",
            unit="worker",
        ):
            device = futures[future]
            _, results = future.result()
            for idx, result in results:
                dataframe.at[idx, "ocr_status"] = result.get("ocr_status", "error")
                dataframe.at[idx, "ocr_error"] = result.get("ocr_error")
                dataframe.at[idx, "ocr_num_pages"] = result.get("ocr_num_pages", 0)
                dataframe.at[idx, "ocr_elapsed_seconds"] = result.get("ocr_elapsed_seconds")
                if result.get("ocr_status") == "success":
                    dataframe.at[idx, "markdown_path"] = result.get("markdown_path", "")
                    dataframe.at[idx, "markdown_content"] = result.get("markdown_content", "")
            save_csv(dataframe, config.articles_with_markdown_path)
            emit_log(
                logger,
                "info",
                f"Completed GLM OCR worker on {device}: {len(results)} PDF(s)",
            )

    persist_ocr_output(dataframe, config, logger)
    emit_log(
        logger,
        "info",
        (
            "GLM OCR complete: "
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
