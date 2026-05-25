import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import json


def configure_logging(log_path: str | None = None, level: str = "INFO"):
    """Configure structured logging for the application.

    Uses a rotating file handler and emits a compact JSON-like message via the formatter.
    """
    log_dir = Path(log_path or "logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler - structured JSON for centralized log collection
    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, level.upper(), logging.INFO))
    ch.setFormatter(
        logging.Formatter('{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
    )
    root.addHandler(ch)

    # Rotating file handler
    fh = RotatingFileHandler(str(log_dir / "app.log"), maxBytes=5_000_000, backupCount=5)
    fh.setLevel(getattr(logging, level.upper(), logging.INFO))
    # simple JSON-ish formatter for easier parsing
    fh.setFormatter(logging.Formatter('{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}'))
    root.addHandler(fh)
