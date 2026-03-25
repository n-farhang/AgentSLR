# eval/run_eval.py
#!/usr/bin/env python3
import argparse
from pathlib import Path

from .abstract_screening_eval import evaluate_abstract_screening
from .fulltext_screening_eval import evaluate_fulltext_screening
from .model_extraction_eval import evaluate_model_extraction
from .parameter_extraction_eval import evaluate_parameter_extraction
from .outbreak_extraction_eval import evaluate_outbreak_extraction
from .utils import SCREENING_PATHOGENS, EXTRACTION_PATHOGENS, OUTBREAK_PATHOGENS


EVAL_TYPES = [
    "abstract_screening",
    "fulltext_screening",
    "model_extraction",
    "parameter_extraction",
    "outbreak_extraction",
]


def main():
    parser = argparse.ArgumentParser(
        description="Run AgentSLR evaluation against PERG ground truth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Abstract screening
  python -m eval.run_eval abstract_screening --pathogen Ebola --screened path/to/abstract_screening_results.csv

  # Fulltext screening
  python -m eval.run_eval fulltext_screening --pathogen Ebola --fulltext-screened path/to/fulltext.csv --abstract-screened path/to/abstract.csv

  # Model extraction
  python -m eval.run_eval model_extraction --pathogen Ebola --extracted path/to/models.csv --fulltext-screening path/to/fulltext.csv

  # Parameter extraction
  python -m eval.run_eval parameter_extraction --pathogen Ebola --extracted path/to/parameters.jsonl --parameter-flagging path/to/screening.jsonl

  # Outbreak extraction
  python -m eval.run_eval outbreak_extraction --pathogen Lassa --extracted path/to/outbreaks.csv --fulltext-screening path/to/fulltext.csv

Valid pathogens:
  - Screening: {screening}
  - Model/Parameter extraction: {extraction}
  - Outbreak extraction: {outbreak}
        """.format(
            screening=", ".join(SCREENING_PATHOGENS),
            extraction=", ".join(EXTRACTION_PATHOGENS),
            outbreak=", ".join(OUTBREAK_PATHOGENS),
        )
    )

    subparsers = parser.add_subparsers(dest="eval_type", help="Evaluation type")

    abstract_parser = subparsers.add_parser("abstract_screening", help="Evaluate abstract screening")
    abstract_parser.add_argument("--pathogen", type=str, required=True)
    abstract_parser.add_argument("--screened", type=Path, required=True)
    abstract_parser.add_argument("--perg-screening", type=Path, default=None)
    abstract_parser.add_argument("--data-dir", type=Path, default=Path("data"))
    abstract_parser.add_argument("--output-dir", type=Path, default=None)
    abstract_parser.add_argument("--identifier", type=str, default=None)

    fulltext_parser = subparsers.add_parser("fulltext_screening", help="Evaluate fulltext screening")
    fulltext_parser.add_argument("--pathogen", type=str, required=True)
    fulltext_parser.add_argument("--fulltext-screened", type=Path, required=True)
    fulltext_parser.add_argument("--abstract-screened", type=Path, required=True)
    fulltext_parser.add_argument("--perg-screening", type=Path, default=None)
    fulltext_parser.add_argument("--data-dir", type=Path, default=Path("data"))
    fulltext_parser.add_argument("--output-dir", type=Path, default=None)
    fulltext_parser.add_argument("--identifier", type=str, default=None)
    fulltext_parser.add_argument("--mode", type=str, default="all",
                                  choices=["all", "fulltext_direct", "perg_conditioned", "ai4epi_abstract_conditioned"])

    model_parser = subparsers.add_parser("model_extraction", help="Evaluate model extraction")
    model_parser.add_argument("--pathogen", type=str, required=True)
    model_parser.add_argument("--extracted", type=Path, required=True)
    model_parser.add_argument("--fulltext-screening", type=Path, default=None)
    model_parser.add_argument("--data-dir", type=Path, default=Path("data"))
    model_parser.add_argument("--output-dir", type=Path, default=None)
    model_parser.add_argument("--identifier", type=str, default=None)

    param_parser = subparsers.add_parser("parameter_extraction", help="Evaluate parameter extraction")
    param_parser.add_argument("--pathogen", type=str, required=True)
    param_parser.add_argument("--extracted", type=Path, required=True)
    param_parser.add_argument("--parameter-flagging", type=Path, default=None)
    param_parser.add_argument("--fulltext-screening", type=Path, default=None)
    param_parser.add_argument("--data-dir", type=Path, default=Path("data"))
    param_parser.add_argument("--output-dir", type=Path, default=None)
    param_parser.add_argument("--identifier", type=str, default=None)

    outbreak_parser = subparsers.add_parser("outbreak_extraction", help="Evaluate outbreak extraction")
    outbreak_parser.add_argument("--pathogen", type=str, required=True)
    outbreak_parser.add_argument("--extracted", type=Path, required=True)
    outbreak_parser.add_argument("--fulltext-screening", type=Path, default=None)
    outbreak_parser.add_argument("--data-dir", type=Path, default=Path("data"))
    outbreak_parser.add_argument("--output-dir", type=Path, default=None)
    outbreak_parser.add_argument("--identifier", type=str, default=None)

    args = parser.parse_args()

    if args.eval_type is None:
        parser.print_help()
        return

    if args.eval_type == "abstract_screening":
        df = evaluate_abstract_screening(
            pathogen=args.pathogen,
            screened_path=args.screened,
            perg_screening_path=args.perg_screening,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            identifier=args.identifier,
        )
    elif args.eval_type == "fulltext_screening":
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
    elif args.eval_type == "model_extraction":
        df = evaluate_model_extraction(
            pathogen=args.pathogen,
            extracted_path=args.extracted,
            fulltext_screening_path=args.fulltext_screening,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            identifier=args.identifier,
        )
    elif args.eval_type == "parameter_extraction":
        df = evaluate_parameter_extraction(
            pathogen=args.pathogen,
            extracted_path=args.extracted,
            parameter_flagging_path=args.parameter_flagging,
            fulltext_screening_path=args.fulltext_screening,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            identifier=args.identifier,
        )
    elif args.eval_type == "outbreak_extraction":
        df = evaluate_outbreak_extraction(
            pathogen=args.pathogen,
            extracted_path=args.extracted,
            fulltext_screening_path=args.fulltext_screening,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            identifier=args.identifier,
        )

    print(f"\n=== {args.eval_type.upper()} Results ===")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
