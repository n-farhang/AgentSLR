# src/analysis/outbreaks/writeup_llm.py
from __future__ import annotations

from pathlib import Path

from src.analysis.llm_refinement import ReportRefinementSpec, run_report_refinement


def _build_stats_text(summary_statistics: dict) -> str:
    return (
        "Dataset Statistics:\n"
        f"- Total outbreak records: {summary_statistics.get('n_records', 'N/A')}\n"
        f"- Source articles: {summary_statistics.get('n_articles', 'N/A')}\n"
        f"- Countries represented: {summary_statistics.get('n_countries', 'N/A')}\n"
        f"- Year range: {summary_statistics.get('year_min', 'N/A')}–{summary_statistics.get('year_max', 'N/A')}\n"
    )


SPEC = ReportRefinementSpec(
    report_type="outbreaks",
    report_label="Outbreak Records",
    raw_md_filename="outbreaks_writeup.md",
    critique_dimensions=[
        "data_fidelity",
        "outbreak_focus",
        "figure_table_presence",
        "traceability",
        "clarity",
        "completeness",
        "interpretation_blocks",
        "formatting",
    ],
    prompt_dir=Path(__file__).resolve().parent.parent / "prompts" / "outbreaks",
    stats_text_builder=_build_stats_text,
    draft_label="first draft written from extracted outbreak records",
)


def run_outbreaks_writeup_llm(config):
    return run_report_refinement(config, SPEC, Path(config.report_outbreaks_dir))
