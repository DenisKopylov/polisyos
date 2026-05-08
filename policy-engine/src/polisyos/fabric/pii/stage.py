"""Public pii stage module API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.fabric.data_plane.tabular import payload_to_dataframe
from polisyos.ir.connectors import FetchResult

from .detector import PresidioConfig, PresidioDetector
from .models import PIIScanResult

logger = get_logger(__name__)


@dataclass(frozen=True)
class PIIDetectionStage:
    """Ingestion stage that annotates FetchResult with PII scan summary."""

    detector: PresidioDetector

    @classmethod
    def from_env(cls) -> PIIDetectionStage | None:
        enabled = _env_bool("POLISYOS_PII_ENABLED", False)
        if not enabled:
            return None

        config = PresidioConfig(
            languages=[
                item.strip()
                for item in os.getenv("POLISYOS_PII_LANGUAGES", "en").split(",")
                if item.strip()
            ],
            score_threshold=_env_float("POLISYOS_PII_SCORE_THRESHOLD", 0.7),
            sample_rate=_env_float("POLISYOS_PII_SAMPLE_RATE", 1.0),
            sample_min_rows=max(1, _env_int("POLISYOS_PII_SAMPLE_MIN_ROWS", 50_000)),
            batch_size=max(1, _env_int("POLISYOS_PII_BATCH_SIZE", 500)),
            max_cached_results=max(1, _env_int("POLISYOS_PII_MAX_CACHE", 512)),
        )

        return cls(detector=PresidioDetector(config=config))

    def process_fetch_result(
        self,
        result: FetchResult[Any],
        *,
        text_columns: list[str] | None = None,
    ) -> tuple[FetchResult[Any], PIIScanResult]:
        df = payload_to_dataframe(result.data)
        if df is None:
            summary = PIIScanResult(total_records_scanned=0, total_entities_found=0)
            return result.model_copy(update={"pii_scan": summary}), summary

        content_hash = result.version.content_hash
        if isinstance(content_hash, str):
            content_hash = content_hash.removeprefix("sha256:")

        scan = self.detector.scan_dataframe(
            df,
            text_columns=text_columns,
            content_hash=content_hash,
        )

        quality_flags = set(result.quality_flags)
        if scan.total_entities_found > 0:
            quality_flags.add(f"pii:{scan.max_severity.value}")

        updated = result.model_copy(
            update={
                "pii_scan": scan,
                "quality_flags": frozenset(quality_flags),
            }
        )

        logger.info(
            "PII scan completed: entities=%d max_severity=%s sampled=%s sample_rate=%.2f duration_ms=%.2f",
            scan.total_entities_found,
            scan.max_severity.value,
            scan.sampled,
            scan.sample_rate,
            scan.scan_duration_ms,
        )
        return updated, scan


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default
