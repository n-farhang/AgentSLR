# src/screening/prompts.py
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


WHO_PATHOGENS = {
    "cchf": "Crimean-Congo haemorrhagic fever virus",
    "rvf": "Rift Valley fever virus",
    "marburg": "Marburg virus",
    "ebola": "Ebola virus",
    "lassa": "Lassa fever or Lassa mammarenavirus",
    "mers": "Middle East respiratory syndrome coronavirus (MERS-CoV)",
    "sars": "Severe Acute Respiratory Syndrome coronavirus (SARS-CoV)",
    "zika": "Zika virus",
    "nipah": "Henipa virus (Nipah virus, Hendra virus)",
}

TEMPLATE_DIR = Path(__file__).with_name("prompt_templates")


@lru_cache(maxsize=None)
def _load_template(filename: str) -> str:
    return (TEMPLATE_DIR / filename).read_text(encoding="utf-8")


def get_study_objectives(pathogen_name: str) -> str:
    template = _load_template("study_objectives.md")
    return template.replace("__PATHOGEN_NAME__", pathogen_name)


def get_abstract_screenprompt(pathogen_name: str) -> str:
    template = _load_template("abstract_screening.md")
    return (
        template.replace("__PATHOGEN_NAME__", pathogen_name)
        .replace("__STUDY_OBJECTIVES__", get_study_objectives(pathogen_name))
    )


def get_fulltext_screenprompt(pathogen_name: str) -> str:
    template = _load_template("fulltext_screening.md")
    return (
        template.replace("__PATHOGEN_NAME__", pathogen_name)
        .replace("__STUDY_OBJECTIVES__", get_study_objectives(pathogen_name))
    )


def get_prompt(stage: str, pathogen: str | None = None) -> str:
    if stage not in {"abstract_screening", "fulltext_review"}:
        raise ValueError(f"No prompt for stage {stage}")

    if pathogen is None:
        raise ValueError(
            f"Stage {stage} requires 'pathogen' parameter. Choose from: {list(WHO_PATHOGENS.keys())}"
        )

    pathogen_name = WHO_PATHOGENS.get(pathogen, pathogen)
    if stage == "abstract_screening":
        return get_abstract_screenprompt(pathogen_name)
    return get_fulltext_screenprompt(pathogen_name)
