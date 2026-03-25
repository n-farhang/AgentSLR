from __future__ import annotations

import logging
from datetime import datetime


def build_logger(logs_root, stage: str, log_level: str) -> logging.Logger:
    logger = logging.getLogger("agentslr_testing")
    logger.setLevel(getattr(logging, log_level))

    if logger.handlers:
        logger.handlers.clear()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_root / f"{stage}_{timestamp}.log"

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger
