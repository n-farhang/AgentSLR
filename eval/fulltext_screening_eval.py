# eval/fulltext_screening_eval.py
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


def compute_fulltext_screening_metrics(
    pathogen: str,
    screened_ft_path: Path,
    screened_abs_path: Path,
    perg_screened_path: Path,
    mode: str = 'all',
    logger=None
) -> Dict:
    df_ft = pd.read_csv(screened_ft_path)
    df_abs = pd.read_csv(screened_abs_path)
    df_perg = pd.read_csv(perg_screened_path)

    cols_to_drop = ['perg_fulltext_result', 'perg_abstract_result', 'Covidence #', 'perg_subset']
    for df in [df_ft, df_abs]:
        drop_cols = [c for c in cols_to_drop if c in df.columns]
        if drop_cols:
            df.drop(columns=drop_cols, inplace=True)

    df_ft = prep_screening_df(df_ft, "markdown_content", "ai4epi_fulltext_decision")
    df_abs = prep_screening_df(df_abs, "abstract", "ai4epi_abstract_decision")

    df_ft = add_perg_columns_from_screening(df_ft, df_perg)
    df_abs = add_perg_columns_from_screening(df_abs, df_perg)

    df_ft = df_ft[df_ft["perg_subset"] == True].reset_index(drop=True)

    if "ai4epi_abstract_decision" not in df_ft.columns:
        df_ft = df_ft.merge(
            df_abs[["article_id", "ai4epi_abstract_decision"]],
            on="article_id", how="left"
        )

    y_true = df_ft["perg_fulltext_result"]

    variants = {
        "fulltext_direct": df_ft["ai4epi_fulltext_decision"],
        "perg_conditioned": df_ft.apply(
            lambda r: "EXCLUDE" if r["perg_abstract_result"] == "EXCLUDE" else r["ai4epi_fulltext_decision"], axis=1
        ),
        "ai4epi_abstract_conditioned": df_ft.apply(
            lambda r: "EXCLUDE" if r["ai4epi_abstract_decision"] == "EXCLUDE" else r["ai4epi_fulltext_decision"], axis=1
        ),
    }

    selected = variants if mode == "all" else {mode: variants[mode]}

    result = {"pathogen": pathogen, "n_eval": len(df_ft)}
    for variant_name, y_pred in selected.items():
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average="macro", zero_division=0
        )
        result[f"precision_{variant_name}"] = float(precision)
        result[f"recall_{variant_name}"] = float(recall)
        result[f"f1_{variant_name}"] = float(f1)

    if logger:
        logger.info(f"{pathogen}: N={len(df_ft)}")
        for variant_name in selected.keys():
            logger.info(
                f"  {variant_name}: P={result[f'precision_{variant_name}']:.4f}, "
                f"R={result[f'recall_{variant_name}']:.4f}, F1={result[f'f1_{variant_name}']:.4f}"
            )

    return result


def compute_all_fulltext_screening(pathogens, agentslr_ft_base, agentslr_abs_base, perg_base, mode='all'):
    all_metrics = []
    for pathogen in pathogens:
        metrics = compute_fulltext_screening_metrics(
            pathogen,
            screened_ft_path=Path(agentslr_ft_base.format(pathogen=pathogen.lower())),
            screened_abs_path=Path(agentslr_abs_base.format(pathogen=pathogen.lower())),
            perg_screened_path=Path(perg_base.format(pathogen=pathogen)),
            mode=mode,
        )
        all_metrics.append(metrics)

    if all_metrics:
        metric_cols = [k for k in all_metrics[0] if k not in ("pathogen", "n_eval")]
        overall = {"pathogen": "Overall", "n_eval": int(sum(m["n_eval"] for m in all_metrics))}
        for col in metric_cols:
            overall[col] = float(pd.Series([m[col] for m in all_metrics]).mean())
        all_metrics.append(overall)

    return pd.DataFrame(all_metrics)


def evaluate_fulltext_screening(
    pathogen: str,
    fulltext_screened_path: Path,
    abstract_screened_path: Path,
    perg_screening_path: Path = None,
    data_dir: Path = None,
    output_dir: Path = None,
    identifier: str = None,
    mode: str = 'all',
) -> pd.DataFrame:
    if data_dir is None:
        data_dir = Path("data")
    if output_dir is None:
        output_dir = Path("data/agentslr/evals/article_screening")
    if identifier is None:
        identifier = fulltext_screened_path.stem

    validate_pathogens([pathogen], SCREENING_PATHOGENS, "fulltext_screening")

    perg_paths = get_perg_paths(pathogen, data_dir)
    if perg_screening_path is None:
        perg_screening_path = perg_paths['screening']

    logger = setup_logger("fulltext_screening_eval", output_dir)
    logger.info(f"Evaluating fulltext screening for pathogen: {pathogen}")
    logger.info(f"Fulltext file: {fulltext_screened_path}")
    logger.info(f"Abstract file: {abstract_screened_path}")
    logger.info(f"Mode: {mode}")

    if not perg_screening_path.exists():
        raise FileNotFoundError(f"PERG screening file not found: {perg_screening_path}")
    if not fulltext_screened_path.exists():
        raise FileNotFoundError(f"Fulltext screened file not found: {fulltext_screened_path}")
    if not abstract_screened_path.exists():
        raise FileNotFoundError(f"Abstract screened file not found: {abstract_screened_path}")

    metrics = compute_fulltext_screening_metrics(
        pathogen,
        screened_ft_path=fulltext_screened_path,
        screened_abs_path=abstract_screened_path,
        perg_screened_path=perg_screening_path,
        mode=mode,
        logger=logger
    )

    df_metrics = pd.DataFrame([metrics])
    if mode == "all":
        df_metrics = df_metrics.rename(columns={
            "precision_ai4epi_abstract_conditioned": "precision",
            "recall_ai4epi_abstract_conditioned": "recall",
            "f1_ai4epi_abstract_conditioned": "f1",
        })
    elif mode == "ai4epi_abstract_conditioned":
        df_metrics = df_metrics.rename(columns={
            "precision_ai4epi_abstract_conditioned": "precision",
            "recall_ai4epi_abstract_conditioned": "recall",
            "f1_ai4epi_abstract_conditioned": "f1",
        })

    output_path = output_dir / f"fulltext_screening_{identifier}.csv"
    df_metrics.to_csv(output_path, index=False)
    logger.info(f"Results saved to: {output_path}")

    save_results({"metrics": [metrics]}, output_dir, "fulltext_screening", identifier)

    return df_metrics


def main():
    parser = argparse.ArgumentParser(description="Evaluate fulltext screening against PERG ground truth")
    parser.add_argument("--pathogen", type=str, required=True, help="Pathogen name")
    parser.add_argument("--fulltext-screened", type=Path, required=True, help="Path to fulltext screening results CSV")
    parser.add_argument("--abstract-screened", type=Path, required=True, help="Path to abstract screening results CSV")
    parser.add_argument("--perg-screening", type=Path, default=None, help="Path to PERG screening CSV (optional)")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Base data directory")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory for results")
    parser.add_argument("--identifier", type=str, default=None, help="Identifier for output files")
    parser.add_argument("--mode", type=str, default="all",
                        choices=["all", "fulltext_direct", "perg_conditioned", "ai4epi_abstract_conditioned"],
                        help="Evaluation mode")
    args = parser.parse_args()

    df = evaluate_fulltext_screening(
        pathogen=args.pathogen,
        fulltext_screened_path=args.fulltext_screened,
        abstract_screened_path=args.abstract_screened,
        perg_screening_path=args.perg_screening,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        identifier=args.identifier,
        mode=args.mode,
    )

    print("\n=== Fulltext Screening Results ===")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
