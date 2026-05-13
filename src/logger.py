import logging
import os
import sys
from datetime import date

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(name)-14s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Terminal — INFO and above (DEBUG is too noisy in Streamlit's terminal output)
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # File — INFO and above (errors, warnings, and key info events; DEBUG is too noisy for a file)
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        log_file = os.path.join(_LOG_DIR, f"stockbreakout_{date.today()}.log")
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as e:
        logger.warning("Could not create log file: %s", e)

    logger.propagate = False
    return logger
