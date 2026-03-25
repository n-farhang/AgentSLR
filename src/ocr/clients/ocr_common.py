# src/ocr/clients/ocr_common.py
import csv
import hashlib
import logging
import os
import shutil
import subprocess
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

import pypdfium2 as pdfium
from PIL import Image
from rapidfuzz.distance import Levenshtein


def now_ts():
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def safe_name(text: str) -> str:
    chars = []
    for char in text:
        if char.isalnum() or char in ("-", "_", "."):
            chars.append(char)
        else:
            chars.append("_")
    return "".join(chars).strip("_") or "doc"


def setup_logging(log_dir: Path, prefix: str, level: str) -> str:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{prefix}_{now_ts()}.log"
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers = []
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    for noisy_name in ("httpx", "httpcore", "urllib3", "huggingface_hub"):
        logging.getLogger(noisy_name).setLevel(logging.WARNING)
    return str(log_path.resolve())


def doc_output_dir(md_root: Path, pdf_path: str) -> Path:
    return md_root / f"{safe_name(Path(pdf_path).stem)}_{sha1(pdf_path)[:10]}"


def render_pdf_pages(pdf_path: str, out_dir: Path, scale: float) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(pdf_path)
    paths = []
    for index in range(len(pdf)):
        page = pdf[index]
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil().convert("RGB")
        path = out_dir / f"page_{index + 1:04d}.png"
        image.save(path)
        paths.append(path)
        image.close()
    pdf.close()
    return paths


def render_pdf_pages_to_pil(pdf_path: str, scale: float) -> list[Image.Image]:
    pdf = pdfium.PdfDocument(pdf_path)
    images = []
    for index in range(len(pdf)):
        page = pdf[index]
        bitmap = page.render(scale=scale)
        images.append(bitmap.to_pil().convert("RGB"))
    pdf.close()
    return images


def temporary_dir(prefix: str):
    return TemporaryDirectory(prefix=prefix)


def extract_pdf_images(pdf_path: str, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / "img"
    proc = subprocess.run(
        ["pdfimages", "-all", pdf_path, str(prefix)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "LC_ALL": "C"},
    )
    if proc.returncode != 0:
        return []
    paths = sorted(path for path in out_dir.iterdir() if path.is_file())
    return [path.name for path in paths]


def extract_pdf_images_by_page(pdf_path: str, out_dir: Path) -> dict[int, list[str]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    list_proc = subprocess.run(
        ["pdfimages", "-list", pdf_path],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
    )
    extract_proc = subprocess.run(
        ["pdfimages", "-all", pdf_path, str(out_dir / "img")],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "LC_ALL": "C"},
    )
    if list_proc.returncode != 0 or extract_proc.returncode != 0:
        return {}
    page_map = {}
    for line in list_proc.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        page_map[int(parts[1])] = int(parts[0])
    grouped = defaultdict(list)
    for path in sorted(path for path in out_dir.iterdir() if path.is_file()):
        stem = path.stem
        if "-" not in stem:
            continue
        try:
            image_num = int(stem.rsplit("-", 1)[1])
        except ValueError:
            continue
        page_num = page_map.get(image_num)
        if page_num is not None:
            grouped[page_num].append(path.name)
    return dict(grouped)


def cleanup_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def write_markdown(out_dir: Path, markdown_text: str) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "document.md"
    md_path.write_text(markdown_text or "", encoding="utf-8", errors="ignore")
    return str(md_path.resolve())


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    cleaned = "\n".join(line.rstrip() for line in lines)
    return cleaned.strip()


def normalized_edit_distance(reference: str, hypothesis: str) -> float:
    reference = normalize_text(reference)
    hypothesis = normalize_text(hypothesis)
    if not reference and not hypothesis:
        return 0.0
    return float(Levenshtein.normalized_distance(reference, hypothesis))


def extract_reference_text(pdf_path: str) -> str:
    proc = subprocess.run(
        ["pdftotext", "-layout", "-nopgbrk", pdf_path, "-"],
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="ignore").strip() or "pdftotext failed")
    return proc.stdout.decode("utf-8", errors="ignore")


def load_pdf_rows(csv_path: str, downloaded_col: str) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if downloaded_col not in reader.fieldnames:
        raise ValueError(f"Missing column: {downloaded_col}")
    return rows


def save_rows_csv(rows: list[dict], out_csv: str, fieldnames: list[str]) -> None:
    with open(out_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
