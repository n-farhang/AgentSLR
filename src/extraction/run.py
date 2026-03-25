# src/extraction/run.py
import sys


def run_data_extraction(config, logger):
    if getattr(config, "use_guided_json", False):
        logger.info("Using guided JSON decoding for extraction (--use-guided-json=True)")
        from .vllm_guided.runners import ModelRunner, OutbreakRunner, ParameterRunner
    elif "gpt-oss" in config.model_name.lower():
        from .models.extraction_responses_api.run import Runner as ModelRunner
        from .outbreaks.extraction_responses_api.run import Runner as OutbreakRunner
        from .parameters.extraction_responses_api.run import Runner as ParameterRunner
    else:
        from .models.extraction.run import Runner as ModelRunner
        from .outbreaks.extraction.run import Runner as OutbreakRunner
        from .parameters.extraction.run import Runner as ParameterRunner

    logger.info("Starting data extraction")

    if config.stage not in [
        "data_extraction",
        "data_extraction_parameters",
        "data_extraction_models",
        "data_extraction_outbreaks",
    ]:
        logger.error(f"Invalid stage '{config.stage}' for data extraction. Exiting.")
        sys.exit(1)

    if config.stage == "data_extraction_parameters":
        logger.info("Extracting parameter data")
        parameter_runner = ParameterRunner(config, logger)
        parameter_runner.run()
        logger.info("Parameter data extraction completed")
        return 0

    if config.stage == "data_extraction_outbreaks":
        logger.info("Extracting outbreak data")
        outbreak_runner = OutbreakRunner(config, logger)
        outbreak_runner.run()
        logger.info("Outbreak data extraction completed")
        return 0

    if config.stage == "data_extraction_models":
        logger.info("Extracting model data")
        model_runner = ModelRunner(config, logger)
        model_runner.run()
        logger.info("Model data extraction completed")
        return 0

    logger.info("Extracting parameter data")
    parameter_runner = ParameterRunner(config, logger)
    parameter_runner.run()

    logger.info("Extracting outbreak data")
    outbreak_runner = OutbreakRunner(config, logger)
    outbreak_runner.run()

    logger.info("Extracting model data")
    model_runner = ModelRunner(config, logger)
    model_runner.run()

    logger.info("Data extraction completed")
    return 0
