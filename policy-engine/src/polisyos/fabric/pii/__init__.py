"""PII detection surface for screening ingested fabric payloads before wider use."""

from polisyos.fabric.pii.detector import PresidioConfig, PresidioDetector
from polisyos.fabric.pii.models import PIIEntity, PIIEntityType, PIIScanResult, PIISeverity
from polisyos.fabric.pii.stage import PIIDetectionStage

__all__ = [
    "PIIDetectionStage",
    "PIIEntity",
    "PIIEntityType",
    "PIIScanResult",
    "PIISeverity",
    "PresidioConfig",
    "PresidioDetector",
]
