# eval/abstract_screening_eval.py
import argparse
from pathlib import Path
from typing import Dict, List

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from .utils import (
    SCREENING_PATHOGENS,
    add_perg_columns_from_screening,
    get_perg_paths,
    save_results,
    setup_logger,
    validate_pathogens,
)


def prep_screening_df(df: pd.DataFrame, content_col: str, decision_col: str) -> pd.DataFrame:
    df = df[df[content_col].notna()].reset_index(drop=True)
    df = df[df[decision_col] != "UNCLEAR"].reset_index(drop=True)
    return df


def compute_abstract_screening_metrics(
    pathogen: str,
    screened_path: Path,
    perg_screened_path: Path,
    logger=None
) -> Dict:
    df_screened = pd.read_csv(screened_path)
    df_perg = pd.read_csv(perg_screened_path)

    cols_to_be_added = ['perg_fulltext_result', 'perg_abstract_result', 'Covidence #', 'perg_subset']

    for col in cols_to_be_added:
        if col in df_screened.columns:
            df_screened = df_screened.drop(columns=col)

    df_abs = add_perg_columns_from_screening(df_screened, df_perg)
    df_abs = prep_screening_df(df_abs, "abstract", "ai4epi_abstract_decision")

    matched_rows = df_abs[df_abs.perg_subset == True]

    y_true = matched_rows['perg_abstract_result']
    y_pred = matched_rows['ai4epi_abstract_decision']

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average='macro', zero_division=0
    )

    if logger:
        logger.info(f"{pathogen}: P={precision:.4f}, R={recall:.4f}, F1={f1:.4f}, N={len(matched_rows)}")

    return {
        "pathogen": pathogen,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "n_eval": int(len(matched_rows)),
    }


def compute_all_abstract_screening(pathogens, agentslr_base, perg_base):
    all_metrics = []
    for pathogen in pathogens:
        screened_path = Path(agentslr_base.format(pathogen=pathogen.lower()))
        perg_screened_path = Path(perg_base.format(pathogen=pathogen))
        metrics = compute_abstract_screening_metrics(pathogen, screened_path, perg_screened_path)
        all_metrics.append(metrics)

    if all_metrics:
        overall_metrics = {
            "pathogen": "Overall",
            "precision": float(pd.Series([m["precision"] for m in all_metrics]).mean()),
            "recall": float(pd.Series([m["recall"] for m in all_metrics]).mean()),
            "f1": float(pd.Series([m["f1"] for m in all_metrics]).mean()),
            "n_eval": int(pd.Series([m["n_eval"] for m in all_metrics]).sum()),
        }
        all_metrics.append(overall_metrics)

    return pd.DataFrame(all_metrics)


def evaluate_abstract_screening(
    pathogen: str,
    screened_path: Path,
    perg_screening_path: Path = None,
    data_dir: Path = None,
    output_dir: Path = None,
    identifier: str = None,
) -> pd.DataFrame:
    if data_dir is None:
        data_dir = Path("data")
    if output_dir is None:
        output_dir = Path("data/agentslr/evals/article_screening")
    if identifier is None:
        identifier = screened_path.stem

    validate_pathogens([pathogen], SCREENING_PATHOGENS, "abstract_screening")

    perg_paths = get_perg_paths(pathogen, data_dir)
    if perg_screening_path is None:
        perg_screening_path = perg_paths['screening']

    logger = setup_logger("abstract_screening_eval", output_dir)
    logger.info(f"Evaluating abstract screening for pathogen: {pathogen}")
    logger.info(f"Screened file: {screened_path}")

    if not perg_screening_path.exists():
        raise FileNotFoundError(f"PERG screening file not found: {perg_screening_path}")
    if not screened_path.exists():
        raise FileNotFoundError(f"Screened file not found: {screened_path}")

    metrics = compute_abstract_screening_metrics(
        pathogen, screened_path, perg_screening_path, logger
    )

    df_metrics = pd.DataFrame([metrics])

    output_path = output_dir / f"abstract_screening_{identifier}.csv"
    df_metrics.to_csv(output_path, index=False)
    logger.info(f"Results saved to: {output_path}")

    save_results({"metrics": [metrics]}, output_dir, "abstract_screening", identifier)

    return df_metrics


def main():
    parser = argparse.ArgumentParser(description="Evaluate abstract screening against PERG ground truth")
    parser.add_argument("--pathogen", type=str, required=True, help="Pathogen name")
    parser.add_argument("--screened", type=Path, required=True, help="Path to abstract screening results CSV")
    parser.add_argument("--perg-screening", type=Path, default=None, help="Path to PERG screening CSV (optional)")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Base data directory")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory for results")
    parser.add_argument("--identifier", type=str, default=None, help="Identifier for output files")
    args = parser.parse_args()

    df = evaluate_abstract_screening(
        pathogen=args.pathogen,
        screened_path=args.screened,
        perg_screening_path=args.perg_screening,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        identifier=args.identifier,
    )

    print("\n=== Abstract Screening Results ===")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
