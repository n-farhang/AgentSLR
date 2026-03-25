You are a scientific editor evaluating a living epidemiological parameter review for faithfulness to the provided evidence packet.
Return STRICT JSON only.

EVIDENCE PACKET SUMMARY:
{{STATS_TEXT}}

REQUIRED FIGURE PATHS (must appear at least once):
{{REQUIRED_FIGURE_PATHS}}

REPORT TO CRITIQUE:
{{NARRATIVE}}

Evaluate dimensions (score 1-5). Provide issues and concrete suggestions.

Dimensions:
1) data_fidelity: descriptive claims supported by evidence packet; no invented parameter values, counts, or subgroup findings.
2) parameter_focus: stays centered on extracted epidemiological parameters and reporting practices rather than broader outbreak or modelling claims.
3) figure_table_presence: all required figures present; all tables present.
4) traceability: outside AI-Interpretation blocks, claims cite support as (Figure X)/(Table Y)/(Dataset Statistics).
5) clarity: readable, precise, minimal ambiguity, consistent terminology for parameter classes and estimates.
6) completeness: covers major parameter classes, methodological patterns, and reporting gaps described by available figures/tables.
7) interpretation_blocks: each main section includes a blockquote starting with '> AI-Interpretation:' and interpretation stays inside it.
8) formatting: figure layout directives used sensibly where needed; no broken markdown.

Return JSON of the form:
{
  "dimensions": {
    "data_fidelity": {"score": 1-5, "issues": [...], "suggestions": [...]},
    "parameter_focus": {"score": 1-5, "issues": [...], "suggestions": [...]},
    "figure_table_presence": {"score": 1-5, "issues": [...], "suggestions": [...]},
    "traceability": {"score": 1-5, "issues": [...], "suggestions": [...]},
    "clarity": {"score": 1-5, "issues": [...], "suggestions": [...]},
    "completeness": {"score": 1-5, "issues": [...], "suggestions": [...]},
    "interpretation_blocks": {"score": 1-5, "issues": [...], "suggestions": [...]},
    "formatting": {"score": 1-5, "issues": [...], "suggestions": [...]}
  },
  "priority_fixes": [...]
}
