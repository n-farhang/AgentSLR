# eval/outbreak_extraction_eval.py
import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .utils import (
    OUTBREAK_PATHOGENS,
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


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
COUNTRIES = [
    'Afghanistan', 'Albania', 'Algeria', 'Andorra', 'Angola',
    'Antigua and Barbuda', 'Argentina', 'Armenia', 'Australia', 'Austria',
    'Azerbaijan', 'Bahamas', 'Bahrain', 'Bangladesh', 'Barbados',
    'Belarus', 'Belgium', 'Belize', 'Benin', 'Bhutan',
    'Bolivia (Plurinational State of)', 'Bosnia and Herzegovina', 'Botswana',
    'Brazil', 'Brunei Darussalam', 'Bulgaria', 'Burkina Faso', 'Burundi',
    'Cabo Verde', 'Cambodia', 'Cameroon', 'Canada', 'Central African Republic',
    'Chad', 'Chile', 'China', 'Colombia', 'Comoros', 'Congo', 'Cook Islands',
    'Costa Rica', "Côte d'Ivoire", 'Croatia', 'Cuba', 'Cyprus',
    'Czechia', "Democratic People's Republic of Korea",
    'Democratic Republic of the Congo', 'Denmark', 'Djibouti', 'Dominica',
    'Dominican Republic', 'Ecuador', 'Egypt', 'El Salvador', 'Equatorial Guinea',
    'Eritrea', 'Estonia', 'Eswatini', 'Ethiopia', 'Fiji', 'Finland', 'France',
    'Gabon', 'Gambia', 'Georgia', 'Germany', 'Ghana', 'Greece', 'Grenada',
    'Guatemala', 'Guinea', 'Guinea-Bissau', 'Guyana', 'Haiti', 'Honduras',
    'Hungary', 'Iceland', 'India', 'Indonesia', 'Iran (Islamic Republic of)',
    'Iraq', 'Ireland', 'Israel', 'Italy', 'Jamaica', 'Japan', 'Jordan',
    'Kazakhstan', 'Kenya', 'Kiribati', 'Kuwait', 'Kyrgyzstan',
    "Lao People's Democratic Republic", 'Latvia', 'Lebanon', 'Lesotho',
    'Liberia', 'Libya', 'Lithuania', 'Luxembourg', 'Madagascar', 'Malawi',
    'Malaysia', 'Maldives', 'Mali', 'Malta', 'Marshall Islands', 'Mauritania',
    'Mauritius', 'Mexico', 'Federated States of Micronesia', 'Monaco',
    'Mongolia', 'Montenegro', 'Morocco', 'Mozambique', 'Myanmar', 'Namibia',
    'Nauru', 'Nepal', 'Netherlands', 'New Zealand', 'Nicaragua', 'Niger',
    'Nigeria', 'Niue', 'North Macedonia', 'Norway', 'Oman', 'Pakistan',
    'Palau', 'Panama', 'Papua New Guinea', 'Paraguay', 'Peru', 'Philippines',
    'Poland', 'Portugal', 'Qatar', 'Republic of Korea', 'Republic of Moldova',
    'Romania', 'Russian Federation', 'Rwanda', 'Saint Kitts and Nevis',
    'Saint Lucia', 'Saint Vincent and the Grenadines', 'Samoa', 'San Marino',
    'Sao Tome and Principe', 'Saudi Arabia', 'Senegal', 'Serbia', 'Seychelles',
    'Sierra Leone', 'Singapore', 'Slovakia', 'Slovenia', 'Solomon Islands',
    'Somalia', 'South Africa', 'South Sudan', 'Spain', 'Sri Lanka', 'Sudan',
    'Suriname', 'Sweden', 'Switzerland', 'Syrian Arab Republic', 'Tajikistan',
    'Thailand', 'Timor-Leste', 'Togo', 'Tonga', 'Trinidad and Tobago',
    'Tunisia', 'Türkiye', 'Turkmenistan', 'Tuvalu', 'Uganda', 'Ukraine',
    'United Arab Emirates',
    'United Kingdom of Great Britain and Northern Ireland',
    'United Republic of Tanzania', 'United States of America', 'Uruguay',
    'Uzbekistan', 'Vanuatu', 'Venezuela (Bolivarian Republic of)', 'Viet Nam',
    'Yemen', 'Yugoslavia', 'Zambia', 'Zimbabwe',
]
MODE_OF_DETECTION = ["Molecular (PCR etc)", "Symptoms", "Confirmed + Suspected", "Unspecified"]
PRE_OUTBREAK_STATUS = ["Disease-free baseline", "Endemic equilibrium", "Unspecified", "Probable"]

FIELD_VALIDATORS = {
    'outbreak_country': (COUNTRIES, False),
    'outbreak_start_month': (MONTHS, False),
    'outbreak_end_month': (MONTHS, False),
    'mode_of_detection': (MODE_OF_DETECTION, False),
    'pre_outbreak': (PRE_OUTBREAK_STATUS, False),
    'outbreak_is_currently_ongoing': (['True', 'False', 'true', 'false', '1', '0', True, False], False),
    'asymptomatic_transmission_described': (['True', 'False', 'true', 'false', '1', '0', True, False], False),
}

OUTBREAK_HIGH_WEIGHT_FIELDS = {
    'outbreak_start_day': 0.5,
    'outbreak_start_month': 0.6,
    'outbreak_start_year': 1.0,
    'outbreak_end_day': 0.5,
    'outbreak_end_month': 0.6,
    'outbreak_end_year': 0.8,
    'cases_confirmed': 1.0,
    'deaths': 1.0,
    'outbreak_country': 1.0,
    'outbreak_location': 0.5,
    'mode_of_detection': 0.7,
    'pre_outbreak': 0.5,
    'outbreak_is_currently_ongoing': 0.4,
    'asymptomatic_transmission_described': 0.4,
}

FIELDS_TO_EVALUATE = [
    ('outbreak_start_day', False),
    ('outbreak_start_month', False),
    ('outbreak_start_year', False),
    ('outbreak_end_day', False),
    ('outbreak_end_month', False),
    ('outbreak_end_year', False),
    ('cases_confirmed', False),
    ('deaths', False),
    ('outbreak_country', False),
    ('outbreak_location', False),
    ('mode_of_detection', False),
    ('pre_outbreak', False),
    ('outbreak_is_currently_ongoing', False),
    ('asymptomatic_transmission_described', False),
]


def is_valid_field_value(val, valid_values, is_multivalue: bool) -> bool:
    if pd.isna(val):
        return True
    valid_set = set(str(v) for v in valid_values)
    if is_multivalue:
        items = [item.strip() for item in str(val).split(';') if item.strip()]
        return all(item in valid_set for item in items)
    return str(val).strip() in valid_set


def filter_invalid_outbreak_rows(df: pd.DataFrame, filter_invalid: bool = True):
    total_rows = len(df)
    if not filter_invalid:
        return df, 0, 0.0

    invalid_mask = pd.Series(False, index=df.index)

    for field_name, (valid_values, is_multivalue) in FIELD_VALIDATORS.items():
        if field_name not in df.columns:
            continue
        for idx, row in df.iterrows():
            if not is_valid_field_value(row[field_name], valid_values, is_multivalue):
                invalid_mask[idx] = True

    invalid_count = int(invalid_mask.sum())
    invalid_pct = (invalid_count / total_rows * 100) if total_rows > 0 else 0.0
    return df.loc[~invalid_mask].copy(), invalid_count, invalid_pct


def normalize_boolean(val):
    if pd.isna(val):
        return None
    if val in [True, 'True', 'true', '1', 1]:
        return True
    if val in [False, 'False', 'false', '0', 0]:
        return False
    return None


def load_outbreak_data(
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

    if 'asymptomatic_transmission_described' not in perg.columns and 'asymptomatic_transmission' in perg.columns:
        perg['asymptomatic_transmission_described'] = perg['asymptomatic_transmission']
    if 'outbreak_is_currently_ongoing' not in perg.columns and 'ongoing' in perg.columns:
        perg['outbreak_is_currently_ongoing'] = perg['ongoing']
    if 'mode_of_detection' not in perg.columns and 'cases_mode_detection' in perg.columns:
        perg['mode_of_detection'] = perg['cases_mode_detection']
    if 'outbreak_start_year' not in perg.columns and 'outbreak_date_year' in perg.columns:
        perg['outbreak_start_year'] = perg['outbreak_date_year']

    if fulltext_screening_path and perg_screening_path and fulltext_screening_path.exists() and perg_screening_path.exists():
        if not ('article_id' in extracted.columns and 'article_uuid' in extracted.columns):
            extracted = map_article_ids_to_covidence(extracted, fulltext_screening_path, perg_screening_path)

    perg['article_id'] = perg['article_id'].astype(str)
    if 'article_id' in extracted.columns:
        extracted['article_id'] = extracted['article_id'].astype(str)

    perg_filtered, perg_invalid_count, perg_invalid_pct = filter_invalid_outbreak_rows(perg, filter_invalid)
    extracted_filtered, extracted_invalid_count, extracted_invalid_pct = filter_invalid_outbreak_rows(extracted, filter_invalid)

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
    }

    return perg_filtered, extracted_filtered, list(common_articles), filter_stats, perg, extracted


def compute_outbreak_field_similarity(val1, val2, field_name: str):
    if pd.isna(val1) and pd.isna(val2):
        return 1.0
    if pd.isna(val1) or pd.isna(val2):
        return 0.0

    if field_name in ['asymptomatic_transmission_described', 'outbreak_is_currently_ongoing']:
        b1 = normalize_boolean(val1)
        b2 = normalize_boolean(val2)
        if b1 is None or b2 is None:
            return 0.0
        return 1.0 if b1 == b2 else 0.0

    if field_name in ['outbreak_start_day', 'outbreak_end_day', 'outbreak_start_year', 'outbreak_end_year', 'cases_confirmed', 'deaths']:
        try:
            return 1.0 if abs(float(val1) - float(val2)) < 0.01 else 0.0
        except Exception:
            return 0.0

    return 1.0 if str(val1).strip() == str(val2).strip() else 0.0


def compute_outbreak_similarity(perg_row: pd.Series, extracted_row: pd.Series) -> float:
    weights = normalise_weights(OUTBREAK_HIGH_WEIGHT_FIELDS)
    sim = 0.0
    for field, weight in weights.items():
        if field not in perg_row.index or field not in extracted_row.index:
            continue
        sim += weight * compute_outbreak_field_similarity(perg_row[field], extracted_row[field], field)
    return sim


def evaluate_outbreak_count_optimal(perg: pd.DataFrame, extracted: pd.DataFrame, common_articles: List[str]) -> Dict[str, float]:
    tp_total = 0
    fp_total = 0
    fn_total = 0

    for article_id in common_articles:
        perg_count = len(perg[perg['article_id'] == article_id])
        extracted_count = len(extracted[extracted['article_id'] == article_id])
        tp_total += min(perg_count, extracted_count)
        fp_total += max(0, extracted_count - perg_count)
        fn_total += max(0, perg_count - extracted_count)

    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    return {'precision': round(precision, 3), 'recall': round(recall, 3), 'f1': round(f1, 3)}


def evaluate_outbreak_field_optimal(
    perg: pd.DataFrame,
    extracted: pd.DataFrame,
    common_articles: List[str],
    field_name: str,
) -> Dict[str, float]:
    tp_total = 0
    fp_total = 0
    fn_total = 0

    for article_id in common_articles:
        perg_outbreaks = perg[perg['article_id'] == article_id]
        extracted_outbreaks = extracted[extracted['article_id'] == article_id]
        matches = optimal_bipartite_matching(perg_outbreaks, extracted_outbreaks, compute_outbreak_similarity)

        for match in matches:
            perg_val = perg.loc[match['perg_idx'], field_name]
            extracted_val = extracted.loc[match['extracted_idx'], field_name]

            if field_name in ['asymptomatic_transmission_described', 'outbreak_is_currently_ongoing']:
                p = normalize_boolean(perg_val)
                e = normalize_boolean(extracted_val)
                if p is None and e is None:
                    tp_total += 1
                elif p is None or e is None:
                    if e is not None:
                        fp_total += 1
                    if p is not None:
                        fn_total += 1
                elif p == e:
                    tp_total += 1
                else:
                    fp_total += 1
                    fn_total += 1
            elif field_name in ['outbreak_start_day', 'outbreak_end_day', 'outbreak_start_year', 'outbreak_end_year', 'cases_confirmed', 'deaths']:
                if pd.isna(perg_val) and pd.isna(extracted_val):
                    tp_total += 1
                elif pd.isna(perg_val) or pd.isna(extracted_val):
                    if not pd.isna(extracted_val):
                        fp_total += 1
                    if not pd.isna(perg_val):
                        fn_total += 1
                else:
                    try:
                        if abs(float(perg_val) - float(extracted_val)) < 0.01:
                            tp_total += 1
                        else:
                            fp_total += 1
                            fn_total += 1
                    except Exception:
                        fp_total += 1
                        fn_total += 1
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

    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    return {'precision': round(precision, 3), 'recall': round(recall, 3), 'f1': round(f1, 3)}


def compute_outbreak_flagging_metrics(
    pathogen: str,
    fulltext_screening_path: Path,
    perg_screening_path: Path,
    outbreaks_extraction_path: Path,
    perg_outbreaks_path: Path,
) -> Dict[str, float]:
    df_outbreaks = load_extracted_data(outbreaks_extraction_path)
    df_perg_outbreaks = pd.read_csv(perg_outbreaks_path)

    metrics = compute_article_flagging_from_screening(
        perg_screening_path=perg_screening_path,
        fulltext_screening_path=fulltext_screening_path,
        perg_extraction_df=df_perg_outbreaks.assign(article_id=df_perg_outbreaks['covidence_id']),
        extracted_df=df_outbreaks.assign(article_id=df_outbreaks['article_id']),
    )

    return {
        'pathogen': pathogen,
        'field': 'Article Flagging',
        'precision': round(metrics['precision'], 3),
        'recall': round(metrics['recall'], 3),
        'f1': round(metrics['f1'], 3),
    }


def evaluate_outbreak_extraction_single(
    pathogen: str,
    extracted_path: Path,
    fulltext_screening_path: Path = None,
    perg_screening_path: Path = None,
    perg_outbreaks_path: Path = None,
    data_dir: Path = None,
    logger=None,
) -> Dict:
    if data_dir is None:
        data_dir = Path("data")

    perg_paths = get_perg_paths(pathogen, data_dir)
    if perg_outbreaks_path is None:
        perg_outbreaks_path = perg_paths['outbreaks']
    if perg_screening_path is None:
        perg_screening_path = perg_paths['screening']

    perg, extracted, common_articles, filter_stats, _, _ = load_outbreak_data(
        pathogen=pathogen,
        perg_path=perg_outbreaks_path,
        extracted_path=extracted_path,
        fulltext_screening_path=fulltext_screening_path,
        perg_screening_path=perg_screening_path,
        filter_invalid=True,
    )

    results = []

    count_metrics = evaluate_outbreak_count_optimal(perg, extracted, common_articles)
    results.append({'pathogen': pathogen, 'field': 'outbreak_count', **count_metrics})

    for field_name, _ in FIELDS_TO_EVALUATE:
        if field_name not in perg.columns or field_name not in extracted.columns:
            continue
        metrics = evaluate_outbreak_field_optimal(perg, extracted, common_articles, field_name)
        results.append({'pathogen': pathogen, 'field': field_name, **metrics})

    if fulltext_screening_path is not None and perg_screening_path is not None:
        results.append(
            compute_outbreak_flagging_metrics(
                pathogen=pathogen,
                fulltext_screening_path=fulltext_screening_path,
                perg_screening_path=perg_screening_path,
                outbreaks_extraction_path=extracted_path,
                perg_outbreaks_path=perg_outbreaks_path,
            )
        )

    if logger:
        logger.info(
            f"{pathogen}: perg_total={filter_stats['perg_total']}, extracted_total={filter_stats['extracted_total']}, "
            f"perg_invalid={filter_stats['perg_invalid']}, extracted_invalid={filter_stats['extracted_invalid']}, "
            f"common_articles={len(common_articles)}"
        )

    return {
        'results': results,
        'filter_stats': filter_stats,
    }


def evaluate_outbreak_extraction(
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
        output_dir = Path("data/agentslr/evals/data_extraction/outbreaks")
    if identifier is None:
        identifier = extracted_path.stem

    validate_pathogens([pathogen], OUTBREAK_PATHOGENS, "outbreak_extraction")

    logger = setup_logger("outbreak_extraction_eval", output_dir)
    logger.info(f"Evaluating outbreak extraction for pathogen: {pathogen}")
    logger.info(f"Extracted file: {extracted_path}")
    if fulltext_screening_path is not None:
        logger.info(f"Fulltext screening file: {fulltext_screening_path}")

    perg_paths = get_perg_paths(pathogen, data_dir)

    if not perg_paths['outbreaks'].exists():
        raise FileNotFoundError(f"PERG outbreaks file not found: {perg_paths['outbreaks']}")
    if not extracted_path.exists():
        raise FileNotFoundError(f"Extracted file not found: {extracted_path}")
    if fulltext_screening_path is not None and not fulltext_screening_path.exists():
        raise FileNotFoundError(f"Fulltext screening file not found: {fulltext_screening_path}")

    result = evaluate_outbreak_extraction_single(
        pathogen=pathogen,
        extracted_path=extracted_path,
        fulltext_screening_path=fulltext_screening_path,
        perg_screening_path=perg_paths['screening'],
        perg_outbreaks_path=perg_paths['outbreaks'],
        data_dir=data_dir,
        logger=logger,
    )

    df = pd.DataFrame(result['results'])

    output_path = output_dir / f"outbreak_extraction_{identifier}_detailed.csv"
    df.to_csv(output_path, index=False)
    logger.info(f"Results saved to: {output_path}")

    save_results(result, output_dir, "outbreak_extraction", identifier)

    return df


def main():
    parser = argparse.ArgumentParser(description="Evaluate outbreak extraction against PERG ground truth")
    parser.add_argument("--pathogen", type=str, required=True, help="Pathogen name (Lassa, Zika)")
    parser.add_argument("--extracted", type=Path, required=True, help="Path to extracted outbreaks file (CSV/JSON/JSONL)")
    parser.add_argument("--fulltext-screening", type=Path, default=None, help="Path to fulltext screening results for notebook-equivalent article flagging")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Base data directory (for PERG files)")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory for results")
    parser.add_argument("--identifier", type=str, default=None, help="Identifier for output files")
    args = parser.parse_args()

    df = evaluate_outbreak_extraction(
        pathogen=args.pathogen,
        extracted_path=args.extracted,
        fulltext_screening_path=args.fulltext_screening,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        identifier=args.identifier,
    )

    print("\n=== Outbreak Extraction Results ===")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
