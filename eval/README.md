# AgentSLR Evaluation Guide

This directory contains evaluation scripts used to compute stage-wise metrics for the AgentSLR pipeline, applied to priority pathogen systematic literature reviews. The metrics are calculated against human annotated labels (PERG).

It covers five evaluation components:

- abstract screening
- full-text screening
- model extraction
- parameter extraction
- outbreak extraction

These python scripts are designed to evaluate user-generated AgentSLR outputs against the PERG reference dataset (available locally in `data/perg` or via Hugging Face: https://huggingface.co/datasets/OxRML/AgentSLR).

## Scope

The scripts in this directory evaluate the following components of the AgentSLR pipeline:

| Evaluation | Script entry point |
| --- | --- |
| Abstract screening | `abstract_screening` |
| Full-text screening | `fulltext_screening` |
| Model extraction | `model_extraction` |
| Parameter extraction | `parameter_extraction` |
| Outbreak extraction | `outbreak_extraction` |

## Evaluation Constructs

The evaluation workflow is organised around the following constructs:

- screening
- flagging
- count
- field-level extraction
- optimal matching between PERG and AgentSLR extractions

### Screening

Screening is evaluated as a binary article-level decision against the PERG reference label:

$$
\mathrm{Precision}=\frac{\mathrm{TP}}{\mathrm{TP}+\mathrm{FP}}, \qquad
\mathrm{Recall}=\frac{\mathrm{TP}}{\mathrm{TP}+\mathrm{FN}}, \qquad
F_1=\frac{2PR}{P+R}
$$

Screening uses macro precision, macro recall and macro F1.

For full-text screening, three variants are evaluated:

| Variant | Meaning |
| --- | --- |
| `ai4epi_abstract_conditioned` | AI abstract to AI full-text |
| `perg_conditioned` | Human abstract to AI full-text |
| `fulltext_direct` | AI direct full-text |

When `fulltext_screening` is run with `--mode all`, the saved `precision`, `recall` and `f1` columns correspond to `ai4epi_abstract_conditioned`.

### Extraction

Extraction is decomposed into three parts: flagging, count and field-level extraction.

#### Flagging

Flagging measures whether the system correctly identifies that a given article contains a given data type.

For parameters this is evaluated over `⟨article, parameter_class⟩` pairs. For models and outbreaks article flagging is computed against the PERG-conditioned full-text pool.

#### Count

Count compares the number of items extracted per article:

$$
\mathrm{TP} = \min(n, \hat{n}), \qquad
\mathrm{FP} = \max(0, \hat{n} - n), \qquad
\mathrm{FN} = \max(0, n - \hat{n})
$$

#### Field-level Extraction

Field-level extraction first aligns PERG and AgentSLR extractions within each article using optimal bipartite matching. The pairwise similarity between a PERG extraction \(E\) and an AgentSLR extraction \(\hat{E}\) is:

$$
s(E, \hat{E}) = \sum_{k \in \mathcal{F}} w_k \cdot d_k(E[k], \hat{E}[k])
$$

For single-value fields, \(d_k\) is exact match. For multi-value fields, \(d_k\) is Jaccard similarity:

$$
d_k(v, \hat{v}) = J(v, \hat{v}) = \frac{|v \cap \hat{v}|}{|v \cup \hat{v}|}
$$

The alignment step uses SciPy's `scipy.optimize.linear_sum_assignment()` over the cost matrix

$$
\mathrm{cost}(E, \hat{E}) = 1 - s(E, \hat{E})
$$

which applies a modified Jonker-Volgenant linear assignment algorithm (Jonker and Volgenant, 1987).

Once matches have been established, field-level precision and recall are computed over the matched pairs.

For multi-value fields, the set-based counts are:

$$
\mathrm{TP} = |v \cap \hat{v}|, \qquad
\mathrm{FP} = |\hat{v} \setminus v|, \qquad
\mathrm{FN} = |v \setminus \hat{v}|
$$

The scripts in this directory preserve the evaluation behaviour for:

- field subsets
- matching logic
- PERG column injection
- output field names
- output column names

## Supported Pathogens

| Evaluation | Supported pathogens |
| --- | --- |
| `abstract_screening` | `Marburg`, `Ebola`, `Lassa`, `SARS`, `Zika`, `MERS`, `Nipah` |
| `fulltext_screening` | `Marburg`, `Ebola`, `Lassa`, `SARS`, `Zika`, `MERS`, `Nipah` |
| `model_extraction` | `Ebola`, `Lassa`, `SARS`, `Zika` |
| `parameter_extraction` | `Ebola`, `Lassa`, `SARS`, `Zika` |
| `outbreak_extraction` | `Lassa`, `Zika` |

## How To Run The Five Evaluations

Run all commands from the repository root:

```bash
python -m eval.run_eval <evaluation> ...
```

The sections below are ordered to follow the pipeline from screening through extraction.

### 1. Abstract Screening

Required input:

- AgentSLR abstract screening CSV

Command template:

```bash
python -m eval.run_eval abstract_screening \
  --pathogen <Pathogen> \
  --screened data/agentslr/client/<model>/<pathogen_lower>/screening/abstract_screening_results.csv \
  --output-dir <output_dir>
```

Example:

```bash
python -m eval.run_eval abstract_screening \
  --pathogen Lassa \
  --screened data/agentslr/client/oss/lassa/screening/abstract_screening_results.csv \
  --output-dir /tmp/agentslr_eval/article_screening
```

### 2. Full-text Screening

Required inputs:

- AgentSLR full-text screening CSV
- AgentSLR abstract screening CSV

Command template:

```bash
python -m eval.run_eval fulltext_screening \
  --pathogen <Pathogen> \
  --fulltext-screened data/agentslr/client/<model>/<pathogen_lower>/screening/fulltext_screening_results.csv \
  --abstract-screened data/agentslr/client/<model>/<pathogen_lower>/screening/abstract_screening_results.csv \
  --mode all \
  --output-dir <output_dir>
```

Example:

```bash
python -m eval.run_eval fulltext_screening \
  --pathogen Lassa \
  --fulltext-screened data/agentslr/client/oss/lassa/screening/fulltext_screening_results.csv \
  --abstract-screened data/agentslr/client/oss/lassa/screening/abstract_screening_results.csv \
  --mode all \
  --output-dir /tmp/agentslr_eval/article_screening
```

### 3. Model Extraction

Required input:

- AgentSLR model extraction file

Recommended input:

- `--fulltext-screening` so the script can reproduce the `Article Flagging` row and perform UUID to covidence mapping when needed

Command template:

```bash
python -m eval.run_eval model_extraction \
  --pathogen <Pathogen> \
  --extracted data/agentslr/client/<model>/<pathogen_lower>/extractions/data_extraction_models.csv \
  --fulltext-screening data/agentslr/client/<model>/<pathogen_lower>/screening/fulltext_screening_results.csv \
  --output-dir <output_dir>
```

Example:

```bash
python -m eval.run_eval model_extraction \
  --pathogen Lassa \
  --extracted data/agentslr/client/oss/lassa/extractions/data_extraction_models.csv \
  --fulltext-screening data/agentslr/client/oss/lassa/screening/fulltext_screening_results.csv \
  --output-dir /tmp/agentslr_eval/data_extraction/models
```

### 4. Parameter Extraction

This evaluator requires two AgentSLR-side inputs.

Required inputs:

- `--extracted`: the parameter extraction file
- `--parameter-flagging`: the parameter screening file used for the `Article Flagging` row

Optional:

- `--fulltext-screening` if the parameter files still use article UUIDs and need covidence mapping

Command template:

```bash
python -m eval.run_eval parameter_extraction \
  --pathogen <Pathogen> \
  --extracted data/agentslr/client/<model>/<pathogen_lower>/extractions/data_extraction_parameters.jsonl \
  --parameter-flagging data/agentslr/client/<model>/<pathogen_lower>/logs/data_extraction_parameters_dumps_<timestamp>/results/screening.jsonl \
  --fulltext-screening data/agentslr/client/<model>/<pathogen_lower>/screening/fulltext_screening_results.csv \
  --output-dir <output_dir>
```

Parameter file locations:

| Input role | Usual location |
| --- | --- |
| Parameter extraction file | `data/agentslr/client/<model>/<pathogen_lower>/extractions/data_extraction_parameters.jsonl` |
| Parameter flagging file | `data/agentslr/client/<model>/<pathogen_lower>/logs/data_extraction_parameters_dumps_*/results/screening.jsonl` |

**Example:**

```bash
python -m eval.run_eval parameter_extraction \
  --pathogen Lassa \
  --extracted data/agentslr/client/oss/lassa/extractions/data_extraction_parameters.jsonl \
  --parameter-flagging data/agentslr/client/oss/lassa/logs/data_extraction_parameters_dumps_2026-02-06_13-35-12/results/screening.jsonl \
  --fulltext-screening data/agentslr/client/oss/lassa/screening/fulltext_screening_results.csv \
  --output-dir /tmp/agentslr_eval/data_extraction/parameters
```

### 5. Outbreak Extraction

Required input:

- AgentSLR outbreak extraction file

Recommended input:

- `--fulltext-screening` so that `Article Flagging` is computed from the full-text screening pool

Command template:

```bash
python -m eval.run_eval outbreak_extraction \
  --pathogen <Pathogen> \
  --extracted data/agentslr/client/<model>/<pathogen_lower>/extractions/data_extraction_outbreaks.csv \
  --fulltext-screening data/agentslr/client/<model>/<pathogen_lower>/screening/fulltext_screening_results.csv \
  --output-dir <output_dir>
```

Example:

```bash
python -m eval.run_eval outbreak_extraction \
  --pathogen Lassa \
  --extracted data/agentslr/client/oss/lassa/extractions/data_extraction_outbreaks.csv \
  --fulltext-screening data/agentslr/client/oss/lassa/screening/fulltext_screening_results.csv \
  --output-dir /tmp/agentslr_eval/data_extraction/outbreaks
```

## Where Ground Truth Comes From

Unless `--data-dir` is overridden, the scripts use the repository ground-truth data under `data/perg/`.

| Purpose | Location pattern |
| --- | --- |
| Screening ground truth | `data/perg/screening/<Pathogen>_filtered.csv` |
| Model ground truth | `data/perg/extracted/<pathogen_lower>_models.csv` |
| Parameter ground truth | `data/perg/extracted/<pathogen_lower>_parameters.csv` |
| Outbreak ground truth | `data/perg/extracted/<pathogen_lower>_outbreaks.csv` |

## Output Files

Each command writes a CSV and a JSON summary to the directory specified by `--output-dir`.

Typical filenames:

- `abstract_screening_<identifier>.csv`
- `fulltext_screening_<identifier>.csv`
- `model_extraction_<identifier>_detailed.csv`
- `parameter_extraction_<identifier>_detailed.csv`
- `outbreak_extraction_<identifier>_detailed.csv`

If `--identifier` is not provided, the script uses the input file stem.

## Jupyter Notebooks (Paper Artefacts)

Jupyter notebooks [article_screening_eval.ipynb](../notebooks/article_screening_eval.ipynb) and [data_extraction_eval.ipynb](../notebooks/data_extraction_eval.ipynb) were used to generate the paper evaluation outputs and follow the same evaluation logic as the scripts in this directory.
