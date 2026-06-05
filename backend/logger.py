import logging
import logging.handlers
from pathlib import Path

_LOG_DIR = Path.home() / "Library" / "Logs" / "mmdview"
_LOG_FILE = _LOG_DIR / "mmdview.log"
_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _setup() -> logging.Logger:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("mmdview")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
    logger.addHandler(handler)
    return logger


logger = _setup()
