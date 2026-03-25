from __future__ import annotations

import json
import re
from pathlib import Path

from src.harvest.queries import get_queries_for_pathogen, normalize_pathogen_name


class Config:
    def __init__(self, args):
        self.stage = args.stage
        self.pathogen = normalize_pathogen_name(args.pathogen)
        if self.pathogen is None:
            raise ValueError(f"Unsupported pathogen: {args.pathogen}")

        self.data_dir = Path(args.data_dir).expanduser().resolve()
        self.model_name = args.model_name
        self.client_dir_name = self._resolve_client_dir_name(args.client_dir_name, self.model_name)
        self.harvest_mode = args.harvest_mode
        self.article_doc_status = args.article_doc_status
        self.ocr_first = args.ocr_first
        if self.ocr_first:
            self.article_doc_status = "ocr_markdown"
        self.fulltext_screening_mode = args.fulltext_screening_mode
        if args.direct_full_text:
            self.fulltext_screening_mode = "direct_fulltext"
        self.direct_full_text = self.fulltext_screening_mode == "direct_fulltext"

        self.harvest_root = self.data_dir / "harvests" / self.pathogen
        self.client_root = self.data_dir / "client" / self.client_dir_name / self.pathogen
        self.ocr_root = self.harvest_root / "ocr"
        self.logs_root = self.client_root / "logs"
        self.screening_root = self.client_root / "screening"
        self.extractions_root = self.client_root / "extractions"
        self.report_dir = self.client_root / args.report_dirname
        self.report_parameters_dir = self.report_dir / "parameters"
        self.report_models_dir = self.report_dir / "models"
        self.report_outbreaks_dir = self.report_dir / "outbreaks"

        self.pdf_dir = self.harvest_root / args.pdf_dirname
        self.harvest_metadata_path = self.harvest_root / args.harvest_metadata_filename
        self.harvest_downloaded_pdfs_path = (
            self.harvest_root / args.harvest_downloaded_pdfs_filename
        )
        self.articles_with_markdown_path = (
            self.harvest_root / args.articles_with_markdown_filename
        )
        self.abstract_screening_path = (
            self.screening_root / args.abstract_screening_filename
        )
        self.fulltext_screening_path = (
            self.screening_root / args.fulltext_screening_filename
        )
        self.data_extraction_parameters_path = (
            self.extractions_root / args.data_extraction_parameters_filename
        )
        self.data_extraction_models_path = (
            self.extractions_root / args.data_extraction_models_filename
        )
        self.data_extraction_outbreaks_path = (
            self.extractions_root / args.data_extraction_outbreaks_filename
        )
        self.report_parameters_md = self.report_parameters_dir / "parameters_writeup.md"
        self.report_parameters_pdf = self.report_parameters_dir / "parameters_writeup.pdf"
        self.report_parameters_manifest = self.report_parameters_dir / "content_manifest.json"
        self.report_models_md = self.report_models_dir / "models_writeup.md"
        self.report_models_pdf = self.report_models_dir / "models_writeup.pdf"
        self.report_models_manifest = self.report_models_dir / "content_manifest.json"
        self.report_outbreaks_md = self.report_outbreaks_dir / "outbreaks_writeup.md"
        self.report_outbreaks_pdf = self.report_outbreaks_dir / "outbreaks_writeup.pdf"
        self.report_outbreaks_manifest = self.report_outbreaks_dir / "content_manifest.json"
        self.progress_output_path = self.harvest_root / args.harvest_progress_filename

        self.metadata_input_path = (
            Path(args.metadata_input).expanduser().resolve()
            if args.metadata_input
            else None
        )
        self.config_json_path = (
            Path(args.config_json).expanduser().resolve()
            if args.config_json
            else None
        )
        self.screening_input_path = (
            Path(args.screening_input).expanduser().resolve()
            if args.screening_input
            else None
        )
        self.ocr_input_path = (
            Path(args.ocr_input).expanduser().resolve()
            if args.ocr_input
            else None
        )

        if self.harvest_mode == "download_only" and self.metadata_input_path is None:
            self.metadata_input_path = self.harvest_metadata_path

        queries = get_queries_for_pathogen(self.pathogen)
        self.pubmed_query = queries["pubmed"]
        self.openalex_query = queries["openalex"]
        self.europepmc_query = queries["europepmc"]

        self.openalex_max = args.openalex_max
        self.pubmed_max = args.pubmed_max
        self.europepmc_max = args.europepmc_max
        self.openalex_per_page = args.openalex_per_page
        self.pubmed_batch = args.pubmed_batch
        self.europepmc_page = args.europepmc_page
        self.openalex_rps = args.openalex_rps
        self.ncbi_rps = args.ncbi_rps
        self.europepmc_rps = args.europepmc_rps
        self.openalex_mailto = args.openalex_mailto
        self.openalex_api_key = args.openalex_api_key
        self.ncbi_api_key = args.ncbi_api_key
        self.ncbi_email = args.ncbi_email
        self.ncbi_tool = args.ncbi_tool
        self.pubmed_sort = args.pubmed_sort
        self.use_europepmc = args.use_europepmc
        self.europepmc_synonym = args.europepmc_synonym
        self.europepmc_sort = args.europepmc_sort
        self.progress_every = args.progress_every
        self.article_downloading_workers = args.article_downloading_workers
        self.unpaywall_email = args.unpaywall_email
        self.log_level = args.log_level

        self._config_json = self._load_config_json()
        self.base_url = args.base_url
        self.api_key = self._resolve_api_key_for_base_url(args.api_key, self.base_url)
        self.mistral_api_key = self._resolve_named_api_key(
            args.mistral_api_key,
            "mistral_api_key",
        )
        self.responses_api = args.responses_api
        self.port = args.port
        self.use_system_prompt = args.use_system_prompt
        self.save_traces = args.save_traces
        self.hit_async = args.hit_async
        self.reasoning_effort = args.reasoning_effort
        self.max_completion_tokens = args.max_completion_tokens
        self.abstract_screening_batch_size = args.abstract_screening_batch_size
        self.abstract_screening_concurrency = args.abstract_screening_concurrency
        self.fulltext_screening_batch_size = args.fulltext_screening_batch_size
        self.fulltext_screening_concurrency = args.fulltext_screening_concurrency
        self.sample_size = args.sample_size
        self.sample_seed = args.sample_seed
        self.ocr_client = args.ocr_client
        self.ocr_input_source = self._normalize_ocr_input_source(args.ocr_input_source)
        self.ocr_client_root = self.ocr_root / self.ocr_client
        self.ocr_markdown_dir = self.ocr_client_root / args.ocr_markdown_dirname
        self.ocr_model_name = args.ocr_model_name
        self.ocr_workers = args.ocr_workers
        self.ocr_skip_existing = args.ocr_skip_existing
        self.ocr_device = args.ocr_device
        self.ocr_dtype = args.ocr_dtype
        self.ocr_pdf_scale = args.ocr_pdf_scale
        self.ocr_page_batch_size = args.ocr_page_batch_size
        self.ocr_max_new_tokens = args.ocr_max_new_tokens
        self.paddle_batch_size = args.paddle_batch_size
        self.paddle_backend = args.paddle_backend
        self.paddle_pipeline_version = args.paddle_pipeline_version
        self.paddle_vllm_url = args.paddle_vllm_url
        self.paddle_vllm_python_bin = args.paddle_vllm_python_bin
        self.paddle_vl_model_name = args.paddle_vl_model_name
        self.paddle_vl_rec_max_concurrency = args.paddle_vl_rec_max_concurrency
        self.paddle_use_queues = args.paddle_use_queues
        self.paddle_enable_hpi = args.paddle_enable_hpi
        self.paddle_precision = args.paddle_precision
        self.paddle_use_tensorrt = args.paddle_use_tensorrt
        self.paddle_start_vllm_server = args.paddle_start_vllm_server
        self.paddle_gpu_memory_utilization = args.paddle_gpu_memory_utilization
        self.paddle_max_num_seqs = args.paddle_max_num_seqs
        self.paddle_max_num_batched_tokens = args.paddle_max_num_batched_tokens
        self.paddle_serve_script = args.paddle_serve_script
        self.data_value_extraction_enabled_bool = (
            args.data_value_extraction_enabled_bool
        )
        self.data_extraction_provenance_enabled = (
            args.data_extraction_provenance_enabled
        )
        self.use_guided_json = args.use_guided_json
        self.parameter_classes = args.parameter_classes
        self.run_id = args.run_id
        self.limit = args.limit
        self.data_extraction_concurrency = args.data_extraction_concurrency
        self.perg_subset = args.perg_subset
        self.report_model_name = args.report_model_name or self.model_name
        self.report_base_url = args.report_base_url or self.base_url
        self.report_api_key = self._resolve_api_key_for_base_url(
            args.report_api_key,
            self.report_base_url,
        )
        self.report_responses_api = (
            self.responses_api
            if args.report_responses_api is None
            else args.report_responses_api
        )
        self.report_reasoning_effort = (
            args.report_reasoning_effort or self.reasoning_effort
        )
        self.report_max_completion_tokens = (
            self.max_completion_tokens
            if args.report_max_completion_tokens is None
            else args.report_max_completion_tokens
        )
        self.writeup_mode = args.writeup_mode
        self.writeup_refinement_iterations = args.writeup_refinement_iterations
        self.writeup_refinement_dirname = args.writeup_refinement_dirname

        self.log_dir = str(self.logs_root)

        self.ensure_directories()
        self.validate()

    def ensure_directories(self) -> None:
        for directory in [
            self.data_dir,
            self.harvest_root,
            self.ocr_root,
            self.ocr_client_root,
            self.ocr_markdown_dir,
            self.logs_root,
            self.screening_root,
            self.extractions_root,
            self.report_dir,
            self.report_parameters_dir,
            self.report_models_dir,
            self.report_outbreaks_dir,
            self.pdf_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        if self.harvest_mode == "download_only" and self.metadata_input_path is None:
            raise ValueError("--metadata-input is required when --harvest-mode=download_only")

        if self.harvest_mode == "download_only" and not self.metadata_input_path.exists():
            raise FileNotFoundError(f"Metadata input not found: {self.metadata_input_path}")

        if self.sample_size is not None and self.sample_size <= 0:
            raise ValueError("--sample-size must be a positive integer")

        if self.ocr_workers <= 0:
            raise ValueError("--ocr-workers must be a positive integer")

        if self.ocr_page_batch_size <= 0:
            raise ValueError("--ocr-page-batch-size must be a positive integer")

        if self.paddle_batch_size <= 0:
            raise ValueError("--paddle-batch-size must be a positive integer")

        if self.data_extraction_concurrency <= 0:
            raise ValueError("--data-extraction-concurrency must be a positive integer")

        if self.writeup_refinement_iterations <= 0:
            raise ValueError("--writeup-refinement-iterations must be a positive integer")

        if (
            self.report_max_completion_tokens is not None
            and self.report_max_completion_tokens <= 0
        ):
            raise ValueError("--report-max-completion-tokens must be a positive integer")

        if self.stage in {"ocr", "convert_pdfs_to_md"} and self.ocr_input_path is not None and not self.ocr_input_path.exists():
            raise FileNotFoundError(f"OCR input not found: {self.ocr_input_path}")

        if self.stage.startswith("data_extraction") and not self.fulltext_screening_path.exists():
            raise FileNotFoundError(
                "Fulltext screening output not found for extraction stage: "
                f"{self.fulltext_screening_path}"
            )

        if self.stage in {"write_up", "write_up_parameters"} and not self.data_extraction_parameters_path.exists():
            raise FileNotFoundError(
                "Parameter extraction output not found for write-up stage: "
                f"{self.data_extraction_parameters_path}"
            )

        if self.stage in {"write_up", "write_up_models"} and not self.data_extraction_models_path.exists():
            raise FileNotFoundError(
                "Model extraction output not found for write-up stage: "
                f"{self.data_extraction_models_path}"
            )

        if self.stage in {"write_up", "write_up_outbreaks"} and not self.data_extraction_outbreaks_path.exists():
            raise FileNotFoundError(
                "Outbreak extraction output not found for write-up stage: "
                f"{self.data_extraction_outbreaks_path}"
            )

    def resolve_abstract_screening_input_path(self) -> Path:
        if self.screening_input_path is not None:
            return self.screening_input_path

        if self.article_doc_status == "ocr_markdown":
            return self.articles_with_markdown_path

        if self.article_doc_status == "metadata":
            return self.harvest_metadata_path

        if self.article_doc_status == "download":
            return self.harvest_downloaded_pdfs_path

        return self.harvest_metadata_path

    def resolve_fulltext_screening_input_path(self) -> Path:
        if self.screening_input_path is not None:
            return self.screening_input_path

        return self.articles_with_markdown_path

    def resolve_markdown_input_path(self) -> Path:
        if self.screening_input_path is not None:
            return self.screening_input_path
        return self.articles_with_markdown_path

    def resolve_ocr_input_path(self) -> Path:
        if self.ocr_input_path is not None:
            return self.ocr_input_path

        if self.screening_input_path is not None:
            return self.screening_input_path

        if self.ocr_input_source == "abstract_screening":
            return self.abstract_screening_path

        return self.harvest_downloaded_pdfs_path

    def _load_config_json(self) -> dict:
        if self.config_json_path is None or not self.config_json_path.exists():
            return {}

        with self.config_json_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}

    def _resolve_api_key_for_base_url(
        self,
        cli_value: str | None,
        base_url: str | None,
    ) -> str | None:
        if cli_value not in {None, "", "6767"}:
            return cli_value
        if "openrouter.ai" in (base_url or "").lower():
            return self._config_json.get("openrouter_api_key", cli_value)
        return self._resolve_named_api_key(cli_value, "openai_api_key")

    def _resolve_named_api_key(
        self,
        cli_value: str | None,
        config_key: str,
    ) -> str | None:
        if cli_value not in {None, "", "6767"}:
            return cli_value
        return self._config_json.get(config_key, cli_value)

    @staticmethod
    def _normalize_ocr_input_source(value: str) -> str:
        mapping = {
            "client": "abstract_screening",
            "global": "harvest_downloaded_pdfs",
        }
        return mapping.get(value, value)

    @staticmethod
    def _resolve_client_dir_name(cli_value: str | None, model_name: str) -> str:
        if cli_value not in {None, ""}:
            candidate = cli_value
        else:
            candidate = model_name

        sanitized = re.sub(r"[^A-Za-z0-9]+", "_", candidate).strip("_").lower()
        if not sanitized:
            raise ValueError("Unable to derive a valid client directory name from the provided value")
        return sanitized
