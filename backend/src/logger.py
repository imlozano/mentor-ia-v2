import os
import sys

from loguru import logger

_DEV_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <7}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "rid=<yellow>{extra[request_id]}</yellow> | "
    "<level>{message}</level>"
)


def setup_logging() -> None:
    """Configura loguru. JSON cuando JSON_LOGS=1, texto coloreado en otro caso."""
    logger.remove()
    logger.configure(extra={"request_id": "-", "request_id_source": "-"})

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    json_logs = os.getenv("JSON_LOGS", "0") == "1"

    if json_logs:
        logger.add(
            sys.stdout,
            level=level,
            serialize=True,
            backtrace=False,
            diagnose=False,
        )
    else:
        logger.add(
            sys.stdout,
            level=level,
            format=_DEV_FORMAT,
            colorize=True,
            backtrace=False,
            diagnose=False,
        )
