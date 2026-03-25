# OCR Stage

The OCR stage converts downloaded PDFs into machine-readable Markdown, preserving document hierarchy, equations (LaTeX) and tables (HTML).

## Process

Each PDF is rendered page-by-page into high-resolution images, then processed with an OCR model to recover text while preserving document structure. The output is a single Markdown file per article.

## Backends

AgentSLR supports three OCR backends:

| Backend | Type | Model | Requirements |
|---------|------|-------|--------------|
| `mistral` | API | `mistral-ocr-2512` | Mistral API key |
| `glm` | Local | `zai-org/GLM-OCR` | GPU, OCR environment |
| `paddle` | Local | `PaddleOCR-VL-0.9B` | GPU or CPU, OCR environment |

### Mistral (Recommended)

Fastest option using the Mistral API. Requires a Mistral API key in `config.json`.

```bash
python main.py --stage ocr \
  --pathogen <pathogen> \
  --data-dir <data-dir> \
  --ocr-client mistral \
  --config-json config.json
```

### GLM (Local)

Local OCR using GLM-OCR. Requires the dedicated OCR environment.

```bash
.venv-ocr/bin/python main.py --stage ocr \
  --pathogen <pathogen> \
  --data-dir <data-dir> \
  --ocr-client glm \
  --ocr-device auto  # or cuda:0, cpu
```

### Paddle (Local)

Lightweight local option using PaddleOCR.

```bash
.venv-ocr/bin/python main.py --stage ocr \
  --pathogen <pathogen> \
  --data-dir <data-dir> \
  --ocr-client paddle \
  --paddle-backend local  # or vllm-server
```

## Key Files

| File | Purpose |
|------|---------|
| `run.py` | OCR orchestration |
| `common.py` | Shared OCR utilities |
| `clients/mistral.py` | Mistral API backend |
| `clients/glm.py` | GLM local backend |
| `clients/paddle.py` | Paddle local backend |

## Outputs

Outputs are written to `<data-dir>/harvests/<pathogen>/`:

| File | Description |
|------|-------------|
| `articles_with_markdown.csv` | Article metadata with markdown content |
| `ocr/<ocr-client>/markdown/` | Individual Markdown files per article |

## Environment Setup

For local OCR backends (GLM or Paddle), create a dedicated environment:

```bash
python3 -m venv .venv-ocr
source .venv-ocr/bin/activate
pip install torch
pip install paddlepaddle  # or paddlepaddle-gpu
pip install -r requirements-ocr.txt
```

## Input Sources

By default, OCR processes articles that passed abstract screening. To run OCR on all downloaded PDFs:

```bash
python main.py --stage ocr \
  --pathogen <pathogen> \
  --data-dir <data-dir> \
  --ocr-client mistral \
  --ocr-input-source harvest_downloaded_pdfs
```
