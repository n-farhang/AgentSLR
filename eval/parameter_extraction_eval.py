# eval/parameter_extraction_eval.py
import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score

from .utils import (
    EXTRACTION_PATHOGENS,
    get_perg_paths,
    map_article_ids_to_covidence,
    normalise_weights,
    optimal_bipartite_matching,
    save_results,
    setup_logger,
    validate_pathogens,
)
from utils.schemas import (
    METHOD_MAPPING,
    PAIRED_UNCERTAINTY_MAPPING,
    PARAMETER_CLASSES_MAPPING,
    PARAMETER_UNITS_MAPPING,
    POPULATION_GROUP_MAPPING,
    POPULATION_SAMPLE_TYPE_MAPPING,
    POPULATION_SEX_MAPPING,
    SINGLE_TYPE_UNCERTAINTY_MAPPING,
    STATISTICAL_APPROACH_MAPPING,
    VALUE_TYPE_MAPPING,
)


UNIT_VALUES = ['days', 'weeks', 'months', 'years', 'hours', 'per_day', 'per_week', 'per_month', 'per_year', 'percentage', 'unspecified']
PROPORTION_TO_PERCENTAGE_CLASSES = {'seroprevalence', 'severity'}

PERG_FIELD_MAPPING = {
    'parameter_unit': 'unit',
    'parameter_value': 'value',
    'parameter_value_type': 'value_type',
    'cfr_ifr_method': 'method',
    'parameter_statistical_approach': 'statistical_approach',
    'parameter_uncertainty_type': 'paired_uncertainty',
    'parameter_uncertainty_singe_type': 'single_type_uncertainty',
    'population_sex': 'population_sex',
    'population_group': 'population_group',
    'population_sample_type': 'population_sample_type',
    'covidence_id': 'article_id',
}

PERG_VALUE_MAPPINGS = {
    'unit': PARAMETER_UNITS_MAPPING,
    'method': METHOD_MAPPING,
    'value_type': VALUE_TYPE_MAPPING,
    'statistical_approach': STATISTICAL_APPROACH_MAPPING,
    'paired_uncertainty': PAIRED_UNCERTAINTY_MAPPING,
    'single_type_uncertainty': SINGLE_TYPE_UNCERTAINTY_MAPPING,
    'population_sex': POPULATION_SEX_MAPPING,
    'population_group': POPULATION_GROUP_MAPPING,
    'population_sample_type': POPULATION_SAMPLE_TYPE_MAPPING,
}

PARAMETER_FIELD_VALIDATORS = {
    'unit': (UNIT_VALUES, False),
}

PARAMETER_HIGH_WEIGHT_FIELDS = {
    'parameter_class': 1,
    'unit': 1,
}

FIELDS_TO_EVALUATE = [
    ('unit', False, False),
    ('value', False, True),
    ('method', False, False),
    ('value_type', False, False),
    ('statistical_approach', False, False),
    ('paired_uncertainty', False, False),
    ('single_type_uncertainty', False, False),
    ('population_sex', False, False),
    ('population_group', False, False),
    ('population_sample_type', False, False),
]


def is_valid_parameter_field_value(val, valid_values, is_multivalue):
    if pd.isna(val):
        return True

    valid_set = set(valid_values)
    if is_multivalue:
        items = [item.strip() for item in str(val).split(';') if item.strip()]
        return all(item in valid_set for item in items)
    return str(val).strip() in valid_set


def filter_invalid_parameter_rows(df, filter_invalid=True):
    total_rows = len(df)

    if not filter_invalid:
        return df, 0, 0.0

    invalid_mask = pd.Series([False] * len(df), index=df.index)

    for field_name, (valid_values, is_multivalue) in PARAMETER_FIELD_VALIDATORS.items():
        if field_name not in df.columns:
            continue

        for idx, row in df.iterrows():
            val = row[field_name]
            if not is_valid_parameter_field_value(val, valid_values, is_multivalue):
                invalid_mask[idx] = True

    invalid_count = int(invalid_mask.sum())
    invalid_pct = (invalid_count / total_rows * 100) if total_rows > 0 else 0

    return df[~invalid_mask].copy(), invalid_count, invalid_pct


def compare_numeric_values(val1, val2, tolerance=1e-9):
    if pd.isna(val1) and pd.isna(val2):
        return True
    if pd.isna(val1) or pd.isna(val2):
        return False
    try:
        num1 = float(val1)
        num2 = float(val2)
        return abs(num1 - num2) <= tolerance
    except (ValueError, TypeError):
        return False


def normalise_extracted_values(df):
    if 'value' not in df.columns or 'parameter_class' not in df.columns:
        return df

    df = df.copy()
    mask = df['parameter_class'].isin(PROPORTION_TO_PERCENTAGE_CLASSES)

    for idx in df[mask].index:
        val = df.loc[idx, 'value']
        if pd.notna(val):
            try:
                num_val = float(val)
                if 0 <= num_val <= 1:
                    df.loc[idx, 'value'] = num_val * 100
            except (ValueError, TypeError):
                pass

    return df


def load_jsonl_extractions(filepath: Path):
    records = []
    with open(filepath, 'r') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                record = {
                    'article_id': data.get('article_id'),
                    'parameter_class': data.get('parameter_class'),
                }
                if 'article_uuid' in data:
                    record['article_uuid'] = data.get('article_uuid')
                if 'covidence_id' in data:
                    record['covidence_id'] = data.get('covidence_id')
                if 'extraction' in data and data['extraction']:
                    for key, value in data['extraction'].items():
                        if key not in ['article_id', 'parameter_class']:
                            record[key] = value
                records.append(record)

    return pd.DataFrame(records)


def load_perg_parameters(filepath: Path):
    df = pd.read_csv(filepath)
    df = df.rename(columns=PERG_FIELD_MAPPING)

    for field_name, mapping in PERG_VALUE_MAPPINGS.items():
        if field_name in df.columns:
            df[field_name] = df[field_name].map(mapping).fillna(df[field_name])

    df = df.loc[:, ~df.columns.duplicated()]
    return df


def prepare_parameter_dataframe(
    df: pd.DataFrame,
    fulltext_screening_path: Path = None,
    perg_screening_path: Path = None,
) -> pd.DataFrame:
    df = df.copy()

    if 'covidence_id' in df.columns:
        if 'article_uuid' not in df.columns and 'article_id' in df.columns:
            df['article_uuid'] = df['article_id']
        df['article_id'] = df['covidence_id']
    elif fulltext_screening_path and perg_screening_path and fulltext_screening_path.exists() and perg_screening_path.exists():
        if not ('article_id' in df.columns and 'article_uuid' in df.columns):
            df = map_article_ids_to_covidence(df, fulltext_screening_path, perg_screening_path)

    df = df.loc[:, ~df.columns.duplicated()]
    return df


def load_parameter_data(
    agentslr_params_file: Path,
    perg_params_file: Path,
    pathogen: str,
    fulltext_screening_path: Path = None,
    perg_screening_path: Path = None,
    filter_invalid: bool = False,
):
    perg = load_perg_parameters(perg_params_file)
    extracted = load_jsonl_extractions(agentslr_params_file) if agentslr_params_file.suffix == '.jsonl' else pd.read_csv(agentslr_params_file)

    perg = perg.loc[:, ~perg.columns.duplicated()]
    extracted = prepare_parameter_dataframe(extracted, fulltext_screening_path, perg_screening_path)
    extracted = extracted.loc[:, ~extracted.columns.duplicated()]

    perg['article_id'] = perg['article_id'].astype(str)
    extracted['article_id'] = extracted['article_id'].astype(str)

    if 'parameter_class' in perg.columns:
        perg['parameter_class'] = perg['parameter_class'].map(PARAMETER_CLASSES_MAPPING).fillna(perg['parameter_class'])

    if 'parameter_class' in perg.columns:
        perg['parameter_class'] = perg['parameter_class'].str.lower().str.replace(' ', '_')
    if 'parameter_class' in extracted.columns:
        extracted['parameter_class'] = extracted['parameter_class'].str.lower().str.replace(' ', '_')

    extracted = normalise_extracted_values(extracted)

    perg_filtered, perg_invalid_count, perg_invalid_pct = filter_invalid_parameter_rows(perg, filter_invalid)
    extracted_filtered, extracted_invalid_count, extracted_invalid_pct = filter_invalid_parameter_rows(extracted, filter_invalid)

    perg_article_ids = set(perg_filtered['article_id'].dropna().tolist())
    extracted_article_ids = set(extracted_filtered['article_id'].dropna().tolist())
    common_articles = perg_article_ids & extracted_article_ids

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

    return perg_filtered, extracted_filtered, list(common_articles), filter_stats


def compute_parameter_similarity(perg_row, extracted_row):
    weights = normalise_weights(PARAMETER_HIGH_WEIGHT_FIELDS)
    similarity = 0.0
    for field, weight in weights.items():
        if field not in perg_row.index or field not in extracted_row.index:
            continue

        perg_val = perg_row[field]
        extracted_val = extracted_row[field]

        if pd.isna(perg_val) and pd.isna(extracted_val):
            field_sim = 1.0
        elif pd.isna(perg_val) or pd.isna(extracted_val):
            field_sim = 0.0
        else:
            field_sim = 1.0 if str(perg_val).strip() == str(extracted_val).strip() else 0.0

        similarity += weight * field_sim

    return similarity


def evaluate_parameter_count_optimal(perg, extracted, common_articles):
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


def evaluate_parameter_field_optimal(perg, extracted, common_articles, field_name, is_multivalue, is_numeric=False):
    tp_total = 0
    fp_total = 0
    fn_total = 0

    for article_id in common_articles:
        perg_params = perg[perg['article_id'] == article_id]
        extracted_params = extracted[extracted['article_id'] == article_id]
        matches = optimal_bipartite_matching(perg_params, extracted_params, compute_parameter_similarity)

        for match in matches:
            perg_val = perg.loc[match['perg_idx'], field_name] if field_name in perg.columns else None
            extracted_val = extracted.loc[match['extracted_idx'], field_name] if field_name in extracted.columns else None

            if is_numeric:
                if compare_numeric_values(perg_val, extracted_val):
                    tp_total += 1
                else:
                    fp_total += 1
                    fn_total += 1
            elif is_multivalue:
                perg_set = {t.strip() for t in str(perg_val).split(';') if t.strip()} if perg_val is not None and not pd.isna(perg_val) else set()
                extracted_set = {t.strip() for t in str(extracted_val).split(';') if t.strip()} if extracted_val is not None and not pd.isna(extracted_val) else set()
                tp_total += len(perg_set & extracted_set)
                fp_total += len(extracted_set - perg_set)
                fn_total += len(perg_set - extracted_set)
            else:
                if (perg_val is None or pd.isna(perg_val)) and (extracted_val is None or pd.isna(extracted_val)):
                    tp_total += 1
                elif perg_val is None or pd.isna(perg_val) or extracted_val is None or pd.isna(extracted_val):
                    if extracted_val is not None and not pd.isna(extracted_val):
                        fp_total += 1
                    if perg_val is not None and not pd.isna(perg_val):
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


def prepare_parameter_flagging_dataframe(
    df: pd.DataFrame,
    fulltext_screening_path: Path = None,
    perg_screening_path: Path = None,
) -> pd.DataFrame:
    df = df.copy()

    if 'covidence_id' in df.columns:
        if 'article_uuid' not in df.columns and 'article_id' in df.columns:
            df['article_uuid'] = df['article_id']
        df['article_id'] = df['covidence_id']
    elif fulltext_screening_path and perg_screening_path and fulltext_screening_path.exists() and perg_screening_path.exists():
        if not ('article_id' in df.columns and 'article_uuid' in df.columns):
            df = map_article_ids_to_covidence(df, fulltext_screening_path, perg_screening_path)

    return df


def compute_parameter_flagging_metrics(
    perg_parameters_file: Path,
    parameter_flagging_file: Path,
    fulltext_screening_path: Path = None,
    perg_screening_path: Path = None,
):
    df_perg_params = pd.read_csv(perg_parameters_file)
    df_agentslr_params_flagging = pd.read_json(parameter_flagging_file, lines=True)
    df_agentslr_params_flagging = prepare_parameter_flagging_dataframe(
        df_agentslr_params_flagging,
        fulltext_screening_path=fulltext_screening_path,
        perg_screening_path=perg_screening_path,
    )

    df_perg_params["parameter_class"] = df_perg_params["parameter_class"].map(PARAMETER_CLASSES_MAPPING)
    df_perg_params = (
        df_perg_params
        .groupby(["covidence_id", "parameter_class"])
        .agg("size")
        .reset_index()
        .drop(0, axis=1)
    )

    df_perg_params['article_id'] = df_perg_params['covidence_id'].astype(int)
    df_agentslr_params_flagging['article_id'] = df_agentslr_params_flagging['article_id'].astype(int)

    df_perg_params = df_perg_params[df_perg_params["article_id"].isin(df_agentslr_params_flagging["article_id"])]
    df_perg_params = df_perg_params[df_perg_params["parameter_class"].isin(df_agentslr_params_flagging["parameter_class"])]

    perg_positive = set(zip(df_perg_params["article_id"], df_perg_params["parameter_class"]))

    df_eval = df_agentslr_params_flagging.copy()
    df_eval["y_true"] = df_eval.apply(lambda r: int((r["article_id"], r["parameter_class"]) in perg_positive), axis=1)
    df_eval["y_pred"] = df_eval["contains_parameter"].astype(int)

    y_true = df_eval["y_true"]
    y_pred = df_eval["y_pred"]

    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    return {
        "precision": round(float(precision), 3),
        "recall": round(float(recall), 3),
        "f1": round(float(f1), 3),
        "n": int(len(df_eval)),
    }


def evaluate_parameter_extraction_single(
    pathogen: str,
    extracted_path: Path,
    parameter_flagging_path: Path = None,
    fulltext_screening_path: Path = None,
    perg_screening_path: Path = None,
    perg_parameters_path: Path = None,
    data_dir: Path = None,
    logger=None,
) -> Dict:
    if data_dir is None:
        data_dir = Path("data")

    perg_paths = get_perg_paths(pathogen, data_dir)
    if perg_parameters_path is None:
        perg_parameters_path = perg_paths['parameters']
    if perg_screening_path is None:
        perg_screening_path = perg_paths['screening']

    perg, extracted, common_articles, filter_stats = load_parameter_data(
        agentslr_params_file=extracted_path,
        perg_params_file=perg_parameters_path,
        pathogen=pathogen,
        fulltext_screening_path=fulltext_screening_path,
        perg_screening_path=perg_screening_path,
        filter_invalid=False,
    )

    results = []

    param_count_metrics = evaluate_parameter_count_optimal(perg, extracted, common_articles)
    results.append({
        'pathogen': pathogen,
        'field': 'parameter_count',
        'precision': param_count_metrics['precision'],
        'recall': param_count_metrics['recall'],
        'f1': param_count_metrics['f1'],
    })

    for field_name, is_multivalue, is_numeric in FIELDS_TO_EVALUATE:
        if field_name not in perg.columns or field_name not in extracted.columns:
            continue

        metrics = evaluate_parameter_field_optimal(perg, extracted, common_articles, field_name, is_multivalue, is_numeric)
        results.append({
            'pathogen': pathogen,
            'field': field_name,
            'precision': metrics['precision'],
            'recall': metrics['recall'],
            'f1': metrics['f1'],
        })

    if parameter_flagging_path is not None:
        flagging_metrics = compute_parameter_flagging_metrics(
            perg_parameters_file=perg_parameters_path,
            parameter_flagging_file=parameter_flagging_path,
            fulltext_screening_path=fulltext_screening_path,
            perg_screening_path=perg_screening_path,
        )
        results.append({
            'pathogen': pathogen,
            'field': 'Article Flagging',
            'precision': flagging_metrics['precision'],
            'recall': flagging_metrics['recall'],
            'f1': flagging_metrics['f1'],
        })

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


def evaluate_parameter_extraction(
    pathogen: str,
    extracted_path: Path,
    parameter_flagging_path: Path = None,
    fulltext_screening_path: Path = None,
    data_dir: Path = None,
    output_dir: Path = None,
    identifier: str = None,
) -> pd.DataFrame:
    if data_dir is None:
        data_dir = Path("data")
    if output_dir is None:
        output_dir = Path("data/agentslr/evals/data_extraction/parameters")
    if identifier is None:
        identifier = extracted_path.stem

    validate_pathogens([pathogen], EXTRACTION_PATHOGENS, "parameter_extraction")

    logger = setup_logger("parameter_extraction_eval", output_dir)
    logger.info(f"Evaluating parameter extraction for pathogen: {pathogen}")
    logger.info(f"Extracted file: {extracted_path}")
    if parameter_flagging_path is not None:
        logger.info(f"Parameter flagging file: {parameter_flagging_path}")
    if fulltext_screening_path is not None:
        logger.info(f"Fulltext screening file: {fulltext_screening_path}")

    perg_paths = get_perg_paths(pathogen, data_dir)

    if not perg_paths['parameters'].exists():
        raise FileNotFoundError(f"PERG parameters file not found: {perg_paths['parameters']}")
    if not extracted_path.exists():
        raise FileNotFoundError(f"Extracted file not found: {extracted_path}")
    if parameter_flagging_path is not None and not parameter_flagging_path.exists():
        raise FileNotFoundError(f"Parameter flagging file not found: {parameter_flagging_path}")
    if fulltext_screening_path is not None and not fulltext_screening_path.exists():
        raise FileNotFoundError(f"Fulltext screening file not found: {fulltext_screening_path}")

    result = evaluate_parameter_extraction_single(
        pathogen=pathogen,
        extracted_path=extracted_path,
        parameter_flagging_path=parameter_flagging_path,
        fulltext_screening_path=fulltext_screening_path,
        perg_screening_path=perg_paths['screening'],
        perg_parameters_path=perg_paths['parameters'],
        data_dir=data_dir,
        logger=logger,
    )

    df = pd.DataFrame(result['results'])

    output_path = output_dir / f"parameter_extraction_{identifier}_detailed.csv"
    df.to_csv(output_path, index=False)
    logger.info(f"Results saved to: {output_path}")

    save_results(result, output_dir, "parameter_extraction", identifier)

    return df


def main():
    parser = argparse.ArgumentParser(description="Evaluate parameter extraction against PERG ground truth")
    parser.add_argument("--pathogen", type=str, required=True, help="Pathogen name (Ebola, Lassa, SARS, Zika)")
    parser.add_argument("--extracted", type=Path, required=True, help="Path to extracted parameters file (JSONL/CSV)")
    parser.add_argument("--parameter-flagging", type=Path, default=None, help="Path to parameter screening JSONL for notebook-equivalent article flagging")
    parser.add_argument("--fulltext-screening", type=Path, default=None, help="Path to fulltext screening results if article IDs still need covidence mapping")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Base data directory (for PERG files)")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory for results")
    parser.add_argument("--identifier", type=str, default=None, help="Identifier for output files")
    args = parser.parse_args()

    df = evaluate_parameter_extraction(
        pathogen=args.pathogen,
        extracted_path=args.extracted,
        parameter_flagging_path=args.parameter_flagging,
        fulltext_screening_path=args.fulltext_screening,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        identifier=args.identifier,
    )

    print("\n=== Parameter Extraction Results ===")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
