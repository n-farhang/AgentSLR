# eval/model_extraction_eval.py
import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .utils import (
    EXTRACTION_PATHOGENS,
    compute_article_flagging_from_screening,
    get_perg_paths,
    load_extracted_data,
    map_article_ids_to_covidence,
    normalise_weights,
    optimal_bipartite_matching,
    save_results,
    setup_logger,
    validate_pathogens,
)


MODEL_TYPES = ['Compartmental', 'Branching process', 'Agent / Individual based', 'Other', 'Unspecified']
COMPARTMENTAL_TYPES = ['SIS', 'SIR', 'SEIR', 'SEIR-SEI', 'SAIR-SEI', 'Not compartmental', 'Other compartmental']
STOCH_DETER = ['Stochastic', 'Deterministic', 'Unspecified']
TRANSMISSION_ROUTES = ['Airborne or close contact', 'Human to human (direct contact)', 'Human to human (direct non-sexual contact)', 'Vector/Animal to human', 'Sexual', 'Unspecified']
ASSUMPTIONS = ['Homogeneous mixing', 'Latent period is same as incubation period', 'Heterogenity in transmission rates - between human groups', 'Heterogenity in transmission rates - between groups', 'Heterogenity in transmission rates - between human and vector', 'Heterogenity in transmission rates - over time', 'Age dependent susceptibility', 'Cross-immunity between Zika and dengue', 'Other', 'Unspecified']
INTERVENTIONS = ['Vaccination', 'Quarantine', 'Vector/Animal control', 'Treatment', 'Contact tracing', 'Hospitals', 'Treatment centres', 'Safe burials', 'Behaviour changes', 'Wolbachia replacement', 'Wolbachia suppression', 'Genetically modified mosquitoes', 'Mechanical removal of breeding sites', 'Pesticides/larvicides', 'Insecticide-treated nets', 'Indoor residual spraying', 'Other', 'Unspecified']
CODING_LANGUAGES = ['R', 'Python', 'Matlab', 'Julia', 'C++', 'Other']
DATA_AVAILABILITY = ['Yes - with a DOI', 'Yes - on Github', 'Yes - as an attachment', 'Yes - on another platform', 'Not available', 'Unspecified']

FIELD_VALIDATORS = {
    'model_type': (MODEL_TYPES, False),
    'compartmental_type': (COMPARTMENTAL_TYPES, False),
    'stoch_deter': (STOCH_DETER, False),
    'transmission_route': (TRANSMISSION_ROUTES, True),
    'assumptions': (ASSUMPTIONS, True),
    'interventions_type': (INTERVENTIONS, True),
    'coding_language': (CODING_LANGUAGES, False),
    'is_data_used_available': (DATA_AVAILABILITY, False),
    'theoretical_model': (['True', 'False', 'true', 'false', '1', '0'], False),
    'code_available': (['True', 'False', 'true', 'false', '1', '0'], False),
    'spatial_model': (['True', 'False', 'true', 'false', '1', '0'], False),
    'spillover_included': (['True', 'False', 'true', 'false', '1', '0'], False),
    'uncertainty_was_considered': (['True', 'False', 'true', 'false', '1', '0'], False),
}

HIGH_WEIGHT_FIELDS = {
    'model_type': 1,
    'compartmental_type': 1,
    'stoch_deter': 1,
    'theoretical_model': 1,
    'assumptions': 1,
    'interventions_type': 1,
    'transmission_route': 1,
}

MULTIVALUE_FIELDS = {'transmission_route', 'assumptions', 'interventions_type'}

FIELDS_TO_EVALUATE = [
    ('model_type', False),
    ('compartmental_type', False),
    ('stoch_deter', False),
    ('transmission_route', True),
    ('theoretical_model', False),
    ('code_available', False),
    ('spatial_model', False),
    ('spillover_included', False),
    ('uncertainty_was_considered', False),
    ('assumptions', True),
    ('interventions_type', True),
]


def is_valid_field_value(val, valid_values: List[str], is_multivalue: bool) -> bool:
    if pd.isna(val):
        return True

    valid_set = set(valid_values)
    if is_multivalue:
        items = [item.strip() for item in str(val).split(';') if item.strip()]
        return all(item in valid_set for item in items)
    return str(val).strip() in valid_set


def filter_invalid_rows(df: pd.DataFrame, filter_invalid: bool = True) -> Tuple[pd.DataFrame, int, float]:
    total_rows = len(df)
    if not filter_invalid:
        return df, 0, 0.0

    invalid_mask = pd.Series([False] * len(df), index=df.index)

    for field_name, (valid_values, is_multivalue) in FIELD_VALIDATORS.items():
        if field_name not in df.columns:
            continue
        for idx, row in df.iterrows():
            val = row[field_name]
            if not is_valid_field_value(val, valid_values, is_multivalue):
                invalid_mask[idx] = True

    invalid_count = int(invalid_mask.sum())
    invalid_pct = (invalid_count / total_rows * 100) if total_rows > 0 else 0.0
    return df[~invalid_mask].copy(), invalid_count, invalid_pct


def load_model_data(
    pathogen: str,
    perg_path: Path,
    extracted_path: Path,
    fulltext_screening_path: Path = None,
    perg_screening_path: Path = None,
    filter_invalid: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, List[str], Dict]:
    perg = pd.read_csv(perg_path)
    extracted = load_extracted_data(extracted_path)

    perg['article_id'] = perg['covidence_id']

    if fulltext_screening_path and perg_screening_path and fulltext_screening_path.exists() and perg_screening_path.exists():
        if not ('article_id' in extracted.columns and 'article_uuid' in extracted.columns):
            extracted = map_article_ids_to_covidence(extracted, fulltext_screening_path, perg_screening_path)

    perg['article_id'] = perg['article_id'].astype(str)
    if 'article_id' in extracted.columns:
        extracted['article_id'] = extracted['article_id'].astype(str)

    perg_filtered, perg_invalid_count, perg_invalid_pct = filter_invalid_rows(perg, filter_invalid)
    extracted_filtered, extracted_invalid_count, extracted_invalid_pct = filter_invalid_rows(extracted, filter_invalid)

    common_articles = set(perg_filtered['article_id'].unique()) & set(extracted_filtered['article_id'].unique())

    perg_filtered = perg_filtered[perg_filtered['article_id'].isin(common_articles)]
    extracted_filtered = extracted_filtered[extracted_filtered['article_id'].isin(common_articles)]

    filter_stats = {
        'pathogen': pathogen,
        'perg_total': len(perg),
        'perg_invalid': perg_invalid_count,
        'perg_invalid_pct': round(perg_invalid_pct, 2),
        'extracted_total': len(extracted),
        'extracted_invalid': extracted_invalid_count,
        'extracted_invalid_pct': round(extracted_invalid_pct, 2),
        'common_articles': len(common_articles),
    }

    return perg_filtered, extracted_filtered, list(common_articles), filter_stats, perg, extracted


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

    return 1.0 if str(val1).strip() == str(val2).strip() else 0.0


def compute_model_similarity(perg_row: pd.Series, extracted_row: pd.Series) -> float:
    weights = normalise_weights(HIGH_WEIGHT_FIELDS)
    similarity = 0.0

    for field, weight in weights.items():
        if field not in perg_row.index or field not in extracted_row.index:
            continue
        is_multivalue = field in MULTIVALUE_FIELDS
        field_sim = compute_field_similarity(perg_row[field], extracted_row[field], is_multivalue)
        similarity += weight * field_sim

    return similarity


def evaluate_screening_optimal(perg: pd.DataFrame, extracted: pd.DataFrame, common_articles: List[str]) -> Dict[str, float]:
    tp_total = 0
    fp_total = 0
    fn_total = 0

    for article_id in common_articles:
        perg_count = len(perg[perg['article_id'] == article_id])
        extracted_count = len(extracted[extracted['article_id'] == article_id])

        tp_total += min(perg_count, extracted_count)
        fp_total += max(0, extracted_count - perg_count)
        fn_total += max(0, perg_count - extracted_count)

    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'precision': round(precision, 3),
        'recall': round(recall, 3),
        'f1': round(f1, 3),
    }


def evaluate_field_optimal(
    perg: pd.DataFrame,
    extracted: pd.DataFrame,
    common_articles: List[str],
    field_name: str,
    is_multivalue: bool,
) -> Dict[str, float]:
    tp_total = 0
    fp_total = 0
    fn_total = 0

    for article_id in common_articles:
        perg_models = perg[perg['article_id'] == article_id]
        extracted_models = extracted[extracted['article_id'] == article_id]

        if field_name == 'compartmental_type':
            perg_models = perg_models[perg_models['model_type'] == 'Compartmental']
            extracted_models = extracted_models[extracted_models['model_type'] == 'Compartmental']

        matches = optimal_bipartite_matching(perg_models, extracted_models, compute_model_similarity)

        for match in matches:
            perg_val = perg.loc[match['perg_idx'], field_name]
            extracted_val = extracted.loc[match['extracted_idx'], field_name]

            if is_multivalue:
                perg_set = {t.strip() for t in str(perg_val).split(';') if t.strip()} if not pd.isna(perg_val) else set()
                extracted_set = {t.strip() for t in str(extracted_val).split(';') if t.strip()} if not pd.isna(extracted_val) else set()
                tp_total += len(perg_set & extracted_set)
                fp_total += len(extracted_set - perg_set)
                fn_total += len(perg_set - extracted_set)
            else:
                if pd.isna(perg_val) and pd.isna(extracted_val):
                    tp_total += 1
                elif pd.isna(perg_val) or pd.isna(extracted_val):
                    if not pd.isna(extracted_val):
                        fp_total += 1
                    if not pd.isna(perg_val):
                        fn_total += 1
                elif str(perg_val).strip() == str(extracted_val).strip():
                    tp_total += 1
                else:
                    fp_total += 1
                    fn_total += 1

    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'precision': round(precision, 3),
        'recall': round(recall, 3),
        'f1': round(f1, 3),
    }


def compute_model_flagging_metrics(
    pathogen: str,
    fulltext_screening_path: Path,
    perg_screening_path: Path,
    models_extraction_path: Path,
    perg_models_path: Path,
) -> Dict[str, float]:
    df_models = load_extracted_data(models_extraction_path)
    df_perg_models = pd.read_csv(perg_models_path)

    metrics = compute_article_flagging_from_screening(
        perg_screening_path=perg_screening_path,
        fulltext_screening_path=fulltext_screening_path,
        perg_extraction_df=df_perg_models.assign(article_id=df_perg_models['covidence_id']),
        extracted_df=df_models.assign(article_id=df_models['article_id']),
    )

    return {
        'pathogen': pathogen,
        'field': 'Article Flagging',
        'precision': round(metrics['precision'], 3),
        'recall': round(metrics['recall'], 3),
        'f1': round(metrics['f1'], 3),
    }


def evaluate_model_extraction_single(
    pathogen: str,
    extracted_path: Path,
    fulltext_screening_path: Path = None,
    perg_screening_path: Path = None,
    perg_models_path: Path = None,
    data_dir: Path = None,
    logger=None,
) -> Dict:
    if data_dir is None:
        data_dir = Path("data")

    perg_paths = get_perg_paths(pathogen, data_dir)
    if perg_models_path is None:
        perg_models_path = perg_paths['models']
    if perg_screening_path is None:
        perg_screening_path = perg_paths['screening']

    perg, extracted, common_articles, filter_stats, _, _ = load_model_data(
        pathogen=pathogen,
        perg_path=perg_models_path,
        extracted_path=extracted_path,
        fulltext_screening_path=fulltext_screening_path,
        perg_screening_path=perg_screening_path,
        filter_invalid=True,
    )

    results = []

    screening_metrics = evaluate_screening_optimal(perg, extracted, common_articles)
    results.append({
        'pathogen': pathogen,
        'field': 'screening',
        'precision': screening_metrics['precision'],
        'recall': screening_metrics['recall'],
        'f1': screening_metrics['f1'],
    })

    model_count_metrics = evaluate_screening_optimal(perg, extracted, common_articles)
    results.append({
        'pathogen': pathogen,
        'field': 'model_count',
        'precision': model_count_metrics['precision'],
        'recall': model_count_metrics['recall'],
        'f1': model_count_metrics['f1'],
    })

    for field_name, is_multivalue in FIELDS_TO_EVALUATE:
        if field_name not in perg.columns or field_name not in extracted.columns:
            continue

        metrics = evaluate_field_optimal(perg, extracted, common_articles, field_name, is_multivalue)
        results.append({
            'pathogen': pathogen,
            'field': field_name,
            'precision': metrics['precision'],
            'recall': metrics['recall'],
            'f1': metrics['f1'],
        })

    if fulltext_screening_path is not None and perg_screening_path is not None:
        results.append(
            compute_model_flagging_metrics(
                pathogen=pathogen,
                fulltext_screening_path=fulltext_screening_path,
                perg_screening_path=perg_screening_path,
                models_extraction_path=extracted_path,
                perg_models_path=perg_models_path,
            )
        )

    if logger:
        logger.info(
            f"{pathogen}: perg_total={filter_stats['perg_total']}, extracted_total={filter_stats['extracted_total']}, "
            f"perg_invalid={filter_stats['perg_invalid']}, extracted_invalid={filter_stats['extracted_invalid']}, "
            f"common_articles={filter_stats['common_articles']}"
        )

    return {
        'results': results,
        'filter_stats': filter_stats,
    }


def evaluate_model_extraction(
    pathogen: str,
    extracted_path: Path,
    fulltext_screening_path: Path = None,
    data_dir: Path = None,
    output_dir: Path = None,
    identifier: str = None,
) -> pd.DataFrame:
    if data_dir is None:
        data_dir = Path("data")
    if output_dir is None:
        output_dir = Path("data/agentslr/evals/data_extraction/models")
    if identifier is None:
        identifier = extracted_path.stem

    validate_pathogens([pathogen], EXTRACTION_PATHOGENS, "model_extraction")

    logger = setup_logger("model_extraction_eval", output_dir)
    logger.info(f"Evaluating model extraction for pathogen: {pathogen}")
    logger.info(f"Extracted file: {extracted_path}")
    if fulltext_screening_path is not None:
        logger.info(f"Fulltext screening file: {fulltext_screening_path}")

    perg_paths = get_perg_paths(pathogen, data_dir)

    if not perg_paths['models'].exists():
        raise FileNotFoundError(f"PERG models file not found: {perg_paths['models']}")
    if not extracted_path.exists():
        raise FileNotFoundError(f"Extracted file not found: {extracted_path}")
    if fulltext_screening_path is not None and not fulltext_screening_path.exists():
        raise FileNotFoundError(f"Fulltext screening file not found: {fulltext_screening_path}")

    result = evaluate_model_extraction_single(
        pathogen=pathogen,
        extracted_path=extracted_path,
        fulltext_screening_path=fulltext_screening_path,
        perg_screening_path=perg_paths['screening'],
        perg_models_path=perg_paths['models'],
        data_dir=data_dir,
        logger=logger,
    )

    df = pd.DataFrame(result['results'])

    output_path = output_dir / f"model_extraction_{identifier}_detailed.csv"
    df.to_csv(output_path, index=False)
    logger.info(f"Results saved to: {output_path}")

    save_results(result, output_dir, "model_extraction", identifier)

    return df


def main():
    parser = argparse.ArgumentParser(description="Evaluate model extraction against PERG ground truth")
    parser.add_argument("--pathogen", type=str, required=True, help="Pathogen name (Ebola, Lassa, SARS, Zika)")
    parser.add_argument("--extracted", type=Path, required=True, help="Path to extracted models file (CSV/JSON/JSONL)")
    parser.add_argument("--fulltext-screening", type=Path, default=None, help="Path to fulltext screening results for notebook-equivalent article flagging")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Base data directory (for PERG files)")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory for results")
    parser.add_argument("--identifier", type=str, default=None, help="Identifier for output files")
    args = parser.parse_args()

    df = evaluate_model_extraction(
        pathogen=args.pathogen,
        extracted_path=args.extracted,
        fulltext_screening_path=args.fulltext_screening,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        identifier=args.identifier,
    )

    print("\n=== Model Extraction Results ===")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
