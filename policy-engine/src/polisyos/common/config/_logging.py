"""Configure the process-wide logging sinks owned by Common bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Protocol, cast


class _SinkLogger(Protocol):
    """Loguru sink operations required by the explicit bootstrap path."""

    def remove(self) -> object: ...

    def add(self, sink: object, **kwargs: object) -> object: ...


def configure_logging_sinks(
    logger: object,
    *,
    log_level: str,
    logs_root: Path | str,
) -> None:
    """Install the console and JSON sinks after the caller's bootstrap checks."""
    sink_logger = cast("_SinkLogger", logger)
    logs_path = Path(logs_root)
    logs_path.mkdir(parents=True, exist_ok=True)
    sink_logger.remove()
    sink_logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )
    sink_logger.add(
        str(logs_path / "system.log"),
        rotation="10 MB",
        retention="10 days",
        serialize=True,
        level="INFO",
        encoding="utf-8",
    )
