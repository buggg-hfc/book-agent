from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_dir: Path | str = "logs") -> logging.Logger:
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("book_agent")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        file_handler = logging.FileHandler(path / "app.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(stream)
        logger.addHandler(file_handler)
    return logger
