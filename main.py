import shlex
import subprocess
import sys
from argparse import Namespace

from args import parse_args
from config import Config
from utils.logger import build_logger


PIPELINE_STAGES = [
    "harvest",
    "abstract_screen",
    "ocr",
    "fulltext_screen",
    "data_extraction_parameters",
    "data_extraction_models",
    "data_extraction_outbreaks",
    "write_up_parameters",
    "write_up_models",
    "write_up_outbreaks",
]

RESUME_STAGE_ALIASES = {
    "convert_pdfs_to_md": "ocr",
    "data_extraction": "data_extraction_parameters",
    "write_up": "write_up_parameters",
}


def run_stage_from_args(args: Namespace) -> int:
    config = Config(args)
    logger = build_logger(config.logs_root, config.stage, config.log_level)
    return dispatch_stage(config, logger)


def dispatch_stage(config, logger) -> int:
    if config.stage == "harvest":
        from src.harvest.pipeline import run_harvest_stage

        return run_harvest_stage(config, logger)

    if config.stage == "abstract_screen":
        from src.screening.abstract import run_abstract_screening

        return run_abstract_screening(config, logger)

    if config.stage in {"ocr", "convert_pdfs_to_md"}:
        from src.ocr.run import run_ocr_stage

        return run_ocr_stage(config, logger)

    if config.stage == "fulltext_screen":
        from src.screening.fulltext import run_fulltext_screening

        return run_fulltext_screening(config, logger)

    if config.stage in {
        "data_extraction",
        "data_extraction_parameters",
        "data_extraction_models",
        "data_extraction_outbreaks",
    }:
        from src.extraction.run import run_data_extraction

        return run_data_extraction(config, logger)

    if config.stage in {
        "write_up",
        "write_up_parameters",
        "write_up_models",
        "write_up_outbreaks",
    }:
        from src.analysis.run import run_writeup_stage

        return run_writeup_stage(config, logger)

    raise SystemExit(f"Unsupported stage: {config.stage}")


def normalize_resume_stage(stage: str) -> str:
    normalized = RESUME_STAGE_ALIASES.get(stage, stage)
    if normalized not in PIPELINE_STAGES:
        raise SystemExit(f"Unsupported --resume-from stage: {stage}")
    return normalized


def build_stage_command(stage: str, argv: list[str]) -> list[str]:
    command = []
    skip_next = False
    stage_replaced = False

    for index, arg in enumerate(argv):
        if skip_next:
            skip_next = False
            continue

        if arg == "--resume-from":
            skip_next = True
            continue
        if arg.startswith("--resume-from="):
            continue

        if arg == "--stage":
            command.extend(["--stage", stage])
            stage_replaced = True
            skip_next = True
            continue

        if arg.startswith("--stage="):
            command.append(f"--stage={stage}")
            stage_replaced = True
            continue

        command.append(arg)

    if not stage_replaced:
        command.extend(["--stage", stage])

    return [sys.executable, "main.py", *command]


def render_shell_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def run_all_stages(args: Namespace, argv: list[str]) -> int:
    resume_from = normalize_resume_stage(args.resume_from)
    start_index = PIPELINE_STAGES.index(resume_from)

    for stage in PIPELINE_STAGES[start_index:]:
        if stage == "ocr" and args.ocr_client in {"glm", "paddle"}:
            if not args.ocr_python_bin:
                resume_command = build_stage_command("run_all", argv)
                resume_command.extend(["--resume-from", "ocr", "--ocr-python-bin", ".venv-ocr/bin/python"])
                print(
                    (
                        f"Reached OCR stage with --ocr-client {args.ocr_client}, which needs the OCR environment.\n"
                        "Resume from OCR after pointing the pipeline at the OCR env python, for example:\n"
                        f"  {render_shell_command(resume_command)}"
                    ),
                    file=sys.stderr,
                )
                return 2

            command = build_stage_command(stage, argv)
            command[0] = args.ocr_python_bin
            result = subprocess.run(command, check=False)
            if result.returncode != 0:
                return result.returncode
            continue

        stage_args = Namespace(**vars(args))
        stage_args.stage = stage
        stage_args.resume_from = stage
        exit_code = run_stage_from_args(stage_args)
        if exit_code != 0:
            return exit_code

    return 0


def main(argv: list[str] | None = None) -> int:
    cli_argv = sys.argv[1:] if argv is None else argv
    args = parse_args(cli_argv)

    if args.stage == "run_all":
        return run_all_stages(args, cli_argv)

    return run_stage_from_args(args)


if __name__ == "__main__":
    raise SystemExit(main())
