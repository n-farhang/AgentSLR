import argparse
import os

from src.harvest.queries import PATHOGEN_CHOICES


def add_core_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--stage",
        choices=[
            "harvest",
            "run_all",
            "abstract_screen",
            "ocr",
            "convert_pdfs_to_md",
            "fulltext_screen",
            "data_extraction",
            "data_extraction_parameters",
            "data_extraction_models",
            "data_extraction_outbreaks",
            "write_up",
            "write_up_parameters",
            "write_up_models",
            "write_up_outbreaks",
        ],
        default="harvest",
    )
    parser.add_argument("--pathogen", choices=PATHOGEN_CHOICES, required=True)
    parser.add_argument("--data-dir", default="data/agentslr")
    parser.add_argument("--resume-from", default="harvest")
    parser.add_argument("--ocr-python-bin", default=os.environ.get("OCR_PYTHON_BIN"))


def add_harvest_flow_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--harvest-mode",
        choices=["full", "metadata_only", "download_only"],
        default="full",
    )
    parser.add_argument("--metadata-input", default=None)
    parser.add_argument("--harvest-metadata-filename", default="harvest_metadata.csv")
    parser.add_argument(
        "--harvest-downloaded-pdfs-filename",
        default="harvest_downloaded_pdfs.csv",
    )
    parser.add_argument("--harvest-progress-filename", default="metadata_progress.csv")
    parser.add_argument("--pdf-dirname", default="pdfs")


def add_harvest_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--openalex-max", type=int, default=50000)
    parser.add_argument("--pubmed-max", type=int, default=30000)
    parser.add_argument("--europepmc-max", type=int, default=20000)
    parser.add_argument("--openalex-per-page", type=int, default=200)
    parser.add_argument("--pubmed-batch", type=int, default=200)
    parser.add_argument("--europepmc-page", type=int, default=1000)
    parser.add_argument("--openalex-rps", type=float, default=10.0)
    parser.add_argument("--ncbi-rps", type=float, default=5.0)
    parser.add_argument("--europepmc-rps", type=float, default=3.0)
    parser.add_argument("--openalex-mailto", default=os.environ.get("OPENALEX_MAILTO"))
    parser.add_argument("--openalex-api-key", default=os.environ.get("OPENALEX_API_KEY"))
    parser.add_argument("--ncbi-api-key", default=os.environ.get("NCBI_API_KEY"))
    parser.add_argument("--ncbi-email", default=os.environ.get("NCBI_EMAIL"))
    parser.add_argument("--ncbi-tool", default="AgentSLR")
    parser.add_argument("--pubmed-sort", default=None)
    parser.add_argument(
        "--use-europepmc",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--europepmc-synonym", default="TRUE")
    parser.add_argument("--europepmc-sort", default=None)
    parser.add_argument("--progress-every", type=int, default=50)
    parser.add_argument("--article-downloading-workers", type=int, default=8)
    parser.add_argument("--unpaywall-email", default=os.environ.get("UNPAYWALL_EMAIL"))


def add_screening_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--screening-input", default=None)
    parser.add_argument("--client-dir-name", default="oss")
    parser.add_argument(
        "--article-doc-status",
        choices=["metadata", "download", "ocr_markdown"],
        default="metadata",
    )
    parser.add_argument(
        "--ocr-first",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--fulltext-screening-mode",
        choices=["direct_fulltext", "on_ai4epi_abstracts", "on_perg_abstracts"],
        default="direct_fulltext",
    )
    parser.add_argument(
        "--articles-with-markdown-filename",
        default="articles_with_markdown.csv",
    )
    parser.add_argument(
        "--abstract-screening-filename",
        default="abstract_screening.csv",
    )
    parser.add_argument(
        "--fulltext-screening-filename",
        default="fulltext_screening.csv",
    )
    parser.add_argument(
        "--model-name",
        default=os.environ.get("OPENAI_MODEL", "openai/gpt-oss-120b"),
    )
    parser.add_argument("--config-json", default="config.json")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL", "http://localhost:6767/v1"),
    )
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", "6767"))
    parser.add_argument(
        "--responses-api",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--use-system-prompt",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--save-traces",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--hit-async",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        default="high",
    )
    parser.add_argument("--max-completion-tokens", type=int, default=65536)
    parser.add_argument("--abstract-screening-batch-size", type=int, default=64)
    parser.add_argument("--abstract-screening-concurrency", type=int, default=8)
    parser.add_argument("--fulltext-screening-batch-size", type=int, default=32)
    parser.add_argument("--fulltext-screening-concurrency", type=int, default=6)
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--sample-seed", type=int, default=7)
    parser.add_argument(
        "--direct-full-text",
        action=argparse.BooleanOptionalAction,
        default=False,
    )


def add_ocr_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--ocr-client",
        choices=["mistral", "glm", "paddle"],
        default="mistral",
    )
    parser.add_argument(
        "--ocr-input-source",
        choices=[
            "abstract_screening",
            "harvest_downloaded_pdfs",
            "client",
            "global",
        ],
        default="abstract_screening",
    )
    parser.add_argument("--ocr-input", default=None)
    parser.add_argument("--ocr-markdown-dirname", default="markdown")
    parser.add_argument("--ocr-model-name", default=None)
    parser.add_argument("--ocr-workers", type=int, default=10)
    parser.add_argument(
        "--ocr-skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--mistral-api-key", default=os.environ.get("MISTRAL_API_KEY"))

    parser.add_argument("--ocr-device", default="auto")
    parser.add_argument("--ocr-dtype", default="bfloat16")
    parser.add_argument("--ocr-pdf-scale", type=float, default=2.0)
    parser.add_argument("--ocr-page-batch-size", type=int, default=8)
    parser.add_argument("--ocr-max-new-tokens", type=int, default=8192)

    parser.add_argument("--paddle-batch-size", type=int, default=4)
    parser.add_argument(
        "--paddle-backend",
        choices=["local", "vllm-server"],
        default="local",
    )
    parser.add_argument("--paddle-pipeline-version", default="v1.5")
    parser.add_argument("--paddle-vllm-url", default="http://localhost:8000/v1")
    parser.add_argument("--paddle-vllm-python-bin", default=None)
    parser.add_argument(
        "--paddle-vl-model-name",
        default="PaddleOCR-VL-0.9B",
    )
    parser.add_argument("--paddle-vl-rec-max-concurrency", type=int, default=32)
    parser.add_argument(
        "--paddle-use-queues",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--paddle-enable-hpi",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument("--paddle-precision", default="fp16")
    parser.add_argument(
        "--paddle-use-tensorrt",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--paddle-start-vllm-server",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument("--paddle-gpu-memory-utilization", type=float, default=0.8)
    parser.add_argument("--paddle-max-num-seqs", type=int, default=128)
    parser.add_argument("--paddle-max-num-batched-tokens", type=int, default=16384)
    parser.add_argument("--paddle-serve-script", default=None)


def add_extraction_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--port", type=int, default=6767)
    parser.add_argument(
        "--data-extraction-parameters-filename",
        default="data_extraction_parameters.jsonl",
    )
    parser.add_argument(
        "--data-extraction-models-filename",
        default="data_extraction_models.csv",
    )
    parser.add_argument(
        "--data-extraction-outbreaks-filename",
        default="data_extraction_outbreaks.csv",
    )
    parser.add_argument(
        "--data-value-extraction-enabled-bool",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--data-extraction-provenance-enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--use-guided-json",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument("--parameter-classes", nargs="+", default=["all"])
    parser.add_argument("--run-id", default="")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--data-extraction-concurrency", type=int, default=4)
    parser.add_argument(
        "--perg-subset",
        action=argparse.BooleanOptionalAction,
        default=False,
    )


def add_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--report-dirname", default="report")
    parser.add_argument("--report-model-name", default=None)
    parser.add_argument("--report-base-url", default=None)
    parser.add_argument("--report-api-key", default=None)
    parser.add_argument(
        "--report-responses-api",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument(
        "--report-reasoning-effort",
        choices=["low", "medium", "high"],
        default=None,
    )
    parser.add_argument("--report-max-completion-tokens", type=int, default=None)
    parser.add_argument(
        "--writeup-mode",
        choices=["raw", "llm", "both"],
        default="both",
    )
    parser.add_argument("--writeup-refinement-iterations", type=int, default=5)
    parser.add_argument(
        "--writeup-refinement-dirname",
        default="llm_refinement",
    )


def add_logging_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AgentSLR testing scaffold for modular pipeline development."
    )
    add_core_args(parser)
    add_harvest_flow_args(parser)
    add_harvest_source_args(parser)
    add_screening_args(parser)
    add_ocr_args(parser)
    add_extraction_args(parser)
    add_report_args(parser)
    add_logging_args(parser)
    return parser.parse_args(argv)
