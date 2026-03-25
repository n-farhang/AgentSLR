# src/analysis/models/writeup_llm.py
from __future__ import annotations

from pathlib import Path

from src.analysis.llm_refinement import ReportRefinementSpec, run_report_refinement


def _build_stats_text(summary_statistics: dict) -> str:
    return (
        "Dataset Statistics:\n"
        f"- Total transmission models extracted: {summary_statistics.get('n_models', 'N/A')}\n"
        f"- Source articles: {summary_statistics.get('n_articles', 'N/A')}\n"
        f"- Deterministic models: {summary_statistics.get('deterministic_n', 'N/A')}\n"
        f"- Stochastic models: {summary_statistics.get('stochastic_n', 'N/A')}\n"
        f"- Models with available code: {summary_statistics.get('code_available_n', 'N/A')}\n"
    )


SPEC = ReportRefinementSpec(
    report_type="models",
    report_label="Transmission Models",
    raw_md_filename="models_writeup.md",
    critique_dimensions=[
        "data_fidelity",
        "model_focus",
        "figure_table_presence",
        "traceability",
        "clarity",
        "completeness",
        "interpretation_blocks",
        "formatting",
    ],
    prompt_dir=Path(__file__).resolve().parent.parent / "prompts" / "models",
    stats_text_builder=_build_stats_text,
    draft_label="first draft written from extracted transmission model records",
)


def run_models_writeup_llm(config):
    return run_report_refinement(config, SPEC, Path(config.report_models_dir))
