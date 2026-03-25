# src/analysis/parameters/writeup_llm.py
from __future__ import annotations

from pathlib import Path

from src.analysis.llm_refinement import ReportRefinementSpec, run_report_refinement


def _build_stats_text(summary_statistics: dict) -> str:
    class_counts = summary_statistics.get("class_counts", {})
    class_lines = "\n".join(
        [f"- {key}: {value}" for key, value in sorted(class_counts.items())]
    )
    return (
        "Dataset Statistics:\n"
        f"- Total parameter extractions: {summary_statistics.get('n_extractions', 'N/A')}\n"
        f"- Source articles: {summary_statistics.get('n_articles', 'N/A')}\n"
        f"- Parameter classes represented: {summary_statistics.get('n_parameter_classes', 'N/A')}\n"
        + ("Parameter class counts:\n" + class_lines if class_lines else "")
    )


SPEC = ReportRefinementSpec(
    report_type="parameters",
    report_label="Epidemiological Parameters",
    raw_md_filename="parameters_writeup.md",
    critique_dimensions=[
        "data_fidelity",
        "parameter_focus",
        "figure_table_presence",
        "traceability",
        "clarity",
        "completeness",
        "interpretation_blocks",
        "formatting",
    ],
    prompt_dir=Path(__file__).resolve().parent.parent / "prompts" / "parameters",
    stats_text_builder=_build_stats_text,
    draft_label="first draft written from extracted epidemiological parameter records",
)


def run_parameters_writeup_llm(config):
    return run_report_refinement(config, SPEC, Path(config.report_parameters_dir))
