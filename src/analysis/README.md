# Analysis Stage

`src/analysis` contains the migrated Stage 6 report generation code.

## Structure

- `run.py`: write-up stage router for `write_up`, `write_up_parameters`, `write_up_models`, and `write_up_outbreaks`
- `parameters/writeup.py`, `models/writeup.py`, `outbreaks/writeup.py`: raw report builders copied from the old pipeline and retargeted to the new config paths
- `parameters/writeup_llm.py`, `models/writeup_llm.py`, `outbreaks/writeup_llm.py`: report-specific wrappers around the shared refinement engine
- `llm_refinement.py`: shared self-refinement loop, API client abstraction, markdown-to-PDF rendering, and artifact promotion
- `prompts/`: report prompts externalised into `.md` files

## Outputs

Each report type writes to `data/agentslr/client/<client>/<pathogen>/<report-dirname>/<report_type>/`.

Raw generation writes:

- `<report_type>_writeup.md`
- `<report_type>_writeup.pdf`
- `content_manifest.json`
- `figures/...`

LLM refinement writes:

- `llm_refinement/iteration_0_initial.md`
- `llm_refinement/iteration_0_reasoning.txt`
- `llm_refinement/iteration_<n>_critique.json`
- `llm_refinement/iteration_<n>_critique_reasoning.txt`
- `llm_refinement/iteration_<n>_refined.md`
- `llm_refinement/iteration_<n>_refinement_reasoning.txt`
- `llm_refinement/final_refined_narrative.md`
- `llm_refinement/final_refined_narrative.pdf`
- `llm_refinement/complete_reasoning_trace.txt`
- `llm_refinement/refinement_summary.json`

The final refined markdown is also promoted back to the top-level report directory as:

- `final_refined_narrative.md`
- the corresponding promoted `<report_type>_writeup.md`

## CLI Controls

The write-up stage uses the standard pipeline args plus report-specific overrides:

- `--report-model-name`
- `--report-base-url`
- `--report-api-key`
- `--report-responses-api` / `--no-report-responses-api`
- `--report-reasoning-effort`
- `--report-max-completion-tokens`
- `--writeup-mode`
- `--writeup-refinement-iterations`
- `--writeup-refinement-dirname`

If a report-specific value is omitted, the stage falls back to the main model settings.
