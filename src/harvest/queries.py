# src/harvest/queries.py

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import tomllib


PATHOGEN_CHOICES = (
    "marburg",
    "ebola",
    "lassa",
    "sars",
    "zika",
    "nipah",
    "rvf",
    "cchf",
    "mers",
)

QUERIES_DIR = Path(__file__).with_name("queries")


@lru_cache(maxsize=None)
def load_query_table(filename: str, table_name: str) -> dict[str, str]:
    path = QUERIES_DIR / filename
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    return data[table_name]


def normalize_pathogen_name(name: str) -> str | None:
    cleaned = name.strip().lower()
    return cleaned if cleaned in PATHOGEN_CHOICES else None


def get_queries_for_pathogen(pathogen: str) -> dict[str, str]:
    normalized = normalize_pathogen_name(pathogen)
    if normalized is None:
        raise ValueError(f"Unsupported pathogen: {pathogen}")

    pubmed = load_query_table("pubmed.toml", "PATHOGEN_QUERIES_PUBMED")
    openalex = load_query_table("openalex.toml", "PATHOGEN_QUERIES_OPENALEX")

    return {
        "pubmed": pubmed[normalized],
        "openalex": openalex[normalized],
        "europepmc": openalex[normalized],
    }
