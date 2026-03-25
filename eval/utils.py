# eval/utils.py
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import precision_recall_fscore_support


VALID_PATHOGENS = ["ebola", "lassa", "marburg", "mers", "nipah", "sars", "zika"]
SCREENING_PATHOGENS = ["Marburg", "Ebola", "Lassa", "SARS", "Zika", "MERS", "Nipah"]
EXTRACTION_PATHOGENS = ["Ebola", "Lassa", "SARS", "Zika"]
OUTBREAK_PATHOGENS = ["Lassa", "Zika"]
VALID_MODELS = ["oss", "deepseek", "kimi", "glm", "gpt"]


def validate_pathogens(pathogens: List[str], valid_set: List[str], eval_type: str) -> List[str]:
    invalid = [p for p in pathogens if p not in valid_set]
    if invalid:
        raise ValueError(
            f"Invalid pathogen(s) for {eval_type}: {invalid}. "
            f"Valid options: {valid_set}"
        )
    return pathogens


def get_perg_paths(pathogen: str, data_dir: Path) -> Dict[str, Path]:
    return {
        'screening': data_dir / f"perg/screening/{pathogen}_filtered.csv",
        'models': data_dir / f"perg/extracted/{pathogen.lower()}_models.csv",
        'parameters': data_dir / f"perg/extracted/{pathogen.lower()}_parameters.csv",
        'outbreaks': data_dir / f"perg/extracted/{pathogen.lower()}_outbreaks.csv",
    }


def setup_logger(name: str, output_dir: Path, pathogen: str = None) -> logging.Logger:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{pathogen}" if pathogen else ""
    log_file = output_dir / f"{name}{suffix}_{timestamp}.log"

    logger = logging.getLogger(f"{name}_{timestamp}")
    logger.setLevel(logging.INFO)
    logger.handlers = []

    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


def f1_from_pr(p: float, r: float) -> float:
    if pd.isna(p) or pd.isna(r):
        return np.nan
    denom = p + r
    return 0.0 if denom == 0 else (2 * p * r) / denom


def add_perg_columns_from_screening(df_harvest: pd.DataFrame, df_perg: pd.DataFrame) -> pd.DataFrame:
    df_h = df_harvest.copy()
    df_p = df_perg.copy()

    cols_to_add = ['perg_fulltext_result', 'perg_abstract_result', 'Covidence #']

    if any(col in df_h.columns for col in cols_to_add + ['perg_subset']):
        df_h = df_h.drop(columns=[col for col in cols_to_add + ['perg_subset'] if col in df_h.columns])

    df_h['_original_index'] = df_h.index

    df_h['doi_clean'] = df_h['doi'].astype(str).str.lower().str.strip()
    df_p['DOI_clean'] = df_p['DOI'].astype(str).str.lower().str.strip()

    df_h['title_clean'] = df_h['title'].astype(str).str.lower().str.strip()
    df_p['Title_clean'] = df_p['Title'].astype(str).str.lower().str.strip()

    df_h['abstract_clean'] = df_h['abstract'].astype(str).str.lower().str.strip()
    df_p['Abstract_clean'] = df_p['Abstract'].astype(str).str.lower().str.strip()

    merged_doi = pd.merge(df_h, df_p[['DOI_clean'] + cols_to_add], left_on='doi_clean', right_on='DOI_clean', how='inner')
    merged_title = pd.merge(df_h, df_p[['Title_clean'] + cols_to_add], left_on='title_clean', right_on='Title_clean', how='inner')
    merged_abstract = pd.merge(df_h, df_p[['Abstract_clean'] + cols_to_add], left_on='abstract_clean', right_on='Abstract_clean', how='inner')

    df_matched = pd.concat([merged_doi, merged_title, merged_abstract], ignore_index=True)
    df_matched = df_matched.drop_duplicates(subset=df_harvest.columns.tolist() + ['_original_index'])

    df_matched['doi_dedup'] = df_matched['doi'].astype(str).str.lower().str.strip()
    df_matched['title_dedup'] = df_matched['title'].astype(str).str.lower().str.strip()
    df_matched['abstract_dedup'] = df_matched['abstract'].astype(str).str.lower().str.strip()

    df_matched = df_matched.drop_duplicates(subset=['doi_dedup'], keep='first')
    df_matched = df_matched.drop_duplicates(subset=['title_dedup'], keep='first')
    df_matched = df_matched.drop_duplicates(subset=['abstract_dedup'], keep='first')

    matched_subset = df_matched[['_original_index'] + cols_to_add].copy()
    matched_subset['perg_subset'] = True

    df_result = df_harvest.copy()
    df_result['_original_index'] = df_result.index

    df_result = df_result.merge(matched_subset, on='_original_index', how='left')
    df_result['perg_subset'] = df_result['perg_subset'].fillna(False)

    df_result = df_result.drop(columns=['_original_index'])

    return df_result


def map_article_ids_to_covidence(
    extracted_df: pd.DataFrame,
    fulltext_screening_path: Path,
    perg_screening_path: Path,
) -> pd.DataFrame:
    if 'article_uuid' in extracted_df.columns and 'article_id' in extracted_df.columns:
        return extracted_df

    if 'covidence_id' in extracted_df.columns:
        df = extracted_df.copy()
        df['article_id'] = df['covidence_id'].astype(str)
        return df

    df_fulltext = pd.read_csv(fulltext_screening_path)
    df_perg = pd.read_csv(perg_screening_path)

    cols_to_drop = ['perg_fulltext_result', 'perg_abstract_result', 'Covidence #', 'perg_subset']
    for col in cols_to_drop:
        if col in df_fulltext.columns:
            df_fulltext = df_fulltext.drop(columns=col)

    df_fulltext = add_perg_columns_from_screening(df_fulltext, df_perg)
    df_fulltext['covidence_id'] = df_fulltext['Covidence #'].apply(
        lambda x: str(x).replace('#', '').strip() if pd.notnull(x) else None
    )

    df = extracted_df.copy()
    original_article_col = 'article_id' if 'article_id' in df.columns else None

    if original_article_col:
        df = df.merge(
            df_fulltext[['article_id', 'covidence_id']],
            on='article_id',
            how='left'
        )
        df = df.rename(columns={'article_id': 'article_uuid', 'covidence_id': 'article_id'})

    return df


def compute_field_similarity(val1, val2, is_multivalue: bool = False) -> float:
    if pd.isna(val1) and pd.isna(val2):
        return 1.0
    if pd.isna(val1) or pd.isna(val2):
        return 0.0

    if is_multivalue:
        set1 = set(str(val1).split(';'))
        set2 = set(str(val2).split(';'))
        if len(set1) == 0 and len(set2) == 0:
            return 1.0
        if len(set1) == 0 or len(set2) == 0:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    else:
        return 1.0 if str(val1).strip() == str(val2).strip() else 0.0


def optimal_bipartite_matching(
    perg_items: pd.DataFrame,
    extracted_items: pd.DataFrame,
    similarity_fn
) -> List[Dict]:
    n_perg = len(perg_items)
    n_extracted = len(extracted_items)

    if n_perg == 0 or n_extracted == 0:
        return []

    similarity_matrix = np.zeros((n_perg, n_extracted))

    for i, (_, perg_row) in enumerate(perg_items.iterrows()):
        for j, (_, extracted_row) in enumerate(extracted_items.iterrows()):
            similarity_matrix[i, j] = similarity_fn(perg_row, extracted_row)

    cost_matrix = 1 - similarity_matrix
    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    matches = []
    for i, j in zip(row_ind, col_ind):
        matches.append({
            'perg_idx': perg_items.index[i],
            'extracted_idx': extracted_items.index[j],
            'similarity': similarity_matrix[i, j]
        })

    return matches


def compute_count_metrics(perg_counts: Dict[str, int], extracted_counts: Dict[str, int]) -> Dict[str, float]:
    all_articles = set(perg_counts.keys()) | set(extracted_counts.keys())

    tp, fp, fn = 0, 0, 0
    for article_id in all_articles:
        n_perg = perg_counts.get(article_id, 0)
        n_extracted = extracted_counts.get(article_id, 0)
        tp += min(n_perg, n_extracted)
        fp += max(0, n_extracted - n_perg)
        fn += max(0, n_perg - n_extracted)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = f1_from_pr(precision, recall)

    return {"precision": precision, "recall": recall, "f1": f1}


def compute_flagging_metrics(
    perg_articles: set,
    extracted_articles: set,
    all_articles: set
) -> Dict[str, float]:
    y_true = [1 if a in perg_articles else 0 for a in all_articles]
    y_pred = [1 if a in extracted_articles else 0 for a in all_articles]

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average='binary', zero_division=0
    )

    return {"precision": float(precision), "recall": float(recall), "f1": float(f1)}


def compute_article_flagging_from_screening(
    perg_screening_path: Path,
    fulltext_screening_path: Path,
    perg_extraction_df: pd.DataFrame,
    extracted_df: pd.DataFrame,
) -> Dict[str, float]:
    df_fulltext = pd.read_csv(fulltext_screening_path)
    df_perg_screening = pd.read_csv(perg_screening_path)

    cols_to_drop = ['perg_fulltext_result', 'perg_abstract_result', 'Covidence #', 'perg_subset']
    for col in cols_to_drop:
        if col in df_fulltext.columns:
            df_fulltext = df_fulltext.drop(columns=col)

    df_fulltext = add_perg_columns_from_screening(df_fulltext, df_perg_screening)
    df_relevant = df_fulltext[df_fulltext['perg_fulltext_result'] == 'INCLUDE'].copy()

    df_relevant['covidence_id'] = df_relevant['Covidence #'].apply(
        lambda x: str(x).replace('#', '').strip() if pd.notnull(x) else None
    )

    extracted_article_ids = set(str(x) for x in extracted_df['article_id'].dropna().unique())
    perg_article_ids = set(str(x) for x in perg_extraction_df['article_id'].dropna().unique())

    df_relevant['ai_flag'] = df_relevant['covidence_id'].apply(
        lambda v: v in extracted_article_ids if pd.notnull(v) else False
    )
    df_relevant['perg_flag'] = df_relevant['covidence_id'].apply(
        lambda v: v in perg_article_ids if pd.notnull(v) else False
    )

    if len(df_relevant) == 0:
        return {"precision": np.nan, "recall": np.nan, "f1": np.nan}

    precision, recall, f1, _ = precision_recall_fscore_support(
        df_relevant['perg_flag'],
        df_relevant['ai_flag'],
        average='macro',
        zero_division=0
    )

    return {"precision": float(precision), "recall": float(recall), "f1": float(f1)}


def save_results(
    results: Dict,
    output_dir: Path,
    eval_type: str,
    identifier: str,
    pathogen: Optional[str] = None
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    suffix = f"_{pathogen}" if pathogen else ""
    filename = f"{eval_type}_{identifier}{suffix}_{timestamp}.json"

    output_path = output_dir / filename
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    return output_path


def normalise_weights(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    return {k: v/total for k, v in weights.items()}


def load_extracted_data(path: Path) -> pd.DataFrame:
    if path.suffix == '.jsonl':
        records = []
        with open(path, 'r') as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    flat = {k: v for k, v in d.items() if k != 'extraction'}
                    if 'extraction' in d and isinstance(d['extraction'], dict):
                        for ek, ev in d['extraction'].items():
                            flat[ek] = ev
                    records.append(flat)
        return pd.DataFrame(records)
    elif path.suffix == '.json':
        with open(path, 'r') as f:
            data = json.load(f)
        if isinstance(data, list):
            return pd.DataFrame(data)
        return pd.DataFrame([data])
    else:
        return pd.read_csv(path)
