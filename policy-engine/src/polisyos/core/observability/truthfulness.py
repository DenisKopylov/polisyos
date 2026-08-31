"""Deprecated compatibility exports for IR-owned truthfulness contracts.

New consumers must import the exact ``polisyos.ir.analytics`` facade. This alias remains
temporarily for same-package Core, repository-tooling, and test consumers that are owned
outside the architecture-imports lane.
"""

import warnings

from polisyos.ir.analytics import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessStatus,
    TruthfulnessTier,
    extract_truthfulness_receipt,
    parse_truthfulness_scope,
    parse_truthfulness_status,
    parse_truthfulness_tier,
    reconcile_truthfulness_tiers,
    truthfulness_depth,
    validate_truthfulness_receipt,
)

__deprecated__ = "Import truthfulness contracts from polisyos.ir.analytics."

warnings.warn(__deprecated__, DeprecationWarning, stacklevel=2)

__all__ = [
    "TruthfulnessReceipt",
    "TruthfulnessScope",
    "TruthfulnessStatus",
    "TruthfulnessTier",
    "extract_truthfulness_receipt",
    "parse_truthfulness_scope",
    "parse_truthfulness_status",
    "parse_truthfulness_tier",
    "reconcile_truthfulness_tiers",
    "truthfulness_depth",
    "validate_truthfulness_receipt",
]
